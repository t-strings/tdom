from dataclasses import dataclass
from string.templatelib import Template
from typing import cast
from collections.abc import Iterable
from functools import lru_cache

from markupsafe import Markup

from ..protocols import HasHTMLDunder
from ..processor import (
    ProcessContext,
    BaseProcessorService,
    _resolve_t_attrs,
    _resolve_html_attrs,
    prep_component_kwargs,
    resolve_text_without_recursion,
    make_ctx,
    extract_embedded_template,
    ComponentObjectProto,
    format_interpolation,
    WalkerProto,
    NormalTextInterpolationValue,
    CachedParserService,
)
from ..callables import get_callable_info
from ..htmlspec import (
    VOID_ELEMENTS,
    RCDATA_CONTENT_ELEMENTS,
    CDATA_CONTENT_ELEMENTS,
    DEFAULT_NORMAL_TEXT_ELEMENT,
)
from .nodes import Fragment, Comment, DocumentType, Element, Text, Node, NodeContainer
from ..parser import (
    TAttribute,
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TFragment,
    TLiteralAttribute,
    TNode,
    TText,
)
from ..utils import CachableTemplate
from ..template_utils import TemplateRef


@dataclass(frozen=True)
class NodeProcessorService(BaseProcessorService):
    """Iteratively process a tdom compatible Template into a `Node` tree."""

    def process_template(
        self, root_template: Template, assume_ctx: ProcessContext | None = None
    ) -> Node:
        root_tnode = self.parser_api.to_tnode(root_template)
        if assume_ctx is None:
            assume_ctx = make_ctx(parent_tag=DEFAULT_NORMAL_TEXT_ELEMENT, ns="html")
        root_node = Fragment()
        q: list[WalkerProto] = [
            self.walk_from_tnode(root_node, root_template, assume_ctx, root_tnode)
        ]
        while q:
            it = q.pop()
            for new_it in it:
                if new_it is not None:
                    q.append(it)
                    q.append(new_it)
                    break
        if len(root_node.children) == 1:
            return root_node.children[0]
        return root_node

    def walk_from_tnode(
        self,
        parent_node: NodeContainer,
        template: Template,
        assume_ctx: ProcessContext,
        root: TNode,
    ) -> Iterable[WalkerProto]:
        q: list[tuple[ProcessContext, TNode, NodeContainer]] = [
            (assume_ctx, root, parent_node)
        ]
        while q:
            last_ctx, tnode, parent_node = q.pop()
            match tnode:
                case TDocumentType(text):
                    if last_ctx.ns != "html":
                        # Nit
                        raise ValueError(
                            "Cannot process document type in subtree of a foreign element."
                        )
                    parent_node.children.append(DocumentType(text))
                case TComment(ref):
                    self._process_comment(parent_node, template, last_ctx, ref)
                case TFragment(children):
                    q.extend(
                        [
                            (last_ctx, tchild, parent_node)
                            for tchild in reversed(children)
                        ]
                    )
                case TComponent(start_i_index, end_i_index, attrs, children):
                    res = self._process_component(
                        parent_node,
                        template,
                        last_ctx,
                        attrs,
                        start_i_index,
                        end_i_index,
                    )
                    if res is not None:
                        yield res
                case TElement(tag, attrs, children):
                    our_ctx = last_ctx.copy(parent_tag=tag)
                    if attrs:
                        resolved_attrs = _resolve_t_attrs(
                            attrs, template.interpolations
                        )
                        el_attrs = _resolve_html_attrs(resolved_attrs)
                    else:
                        el_attrs = {}
                    el = Element(tag, attrs=el_attrs, children=[])
                    parent_node.children.append(el)
                    if tag not in VOID_ELEMENTS:  # Or just check children?
                        q.extend(
                            [(our_ctx, tchild, el) for tchild in reversed(children)]
                        )
                case TText(ref):
                    if last_ctx.parent_tag is None:
                        raise NotImplementedError(
                            "We cannot interpolate texts without knowing what tag they are contained in."
                        )
                    elif last_ctx.parent_tag in CDATA_CONTENT_ELEMENTS:
                        # Must be handled all at once.
                        self._process_raw_texts(parent_node, template, last_ctx, ref)
                    elif last_ctx.parent_tag in RCDATA_CONTENT_ELEMENTS:
                        # We can handle all at once because there are no non-text children and everything must be string-ified.
                        self._process_escapable_raw_texts(
                            parent_node, template, last_ctx, ref
                        )
                    else:
                        for part in ref:
                            if isinstance(part, str):
                                parent_node.children.append(Text(part))
                            else:
                                res = self._process_normal_text(
                                    parent_node, template, last_ctx, part
                                )
                                if res is not None:
                                    yield res
                case _:
                    raise ValueError(f"Unrecognized tnode: {tnode}")

    def _process_comment(
        self,
        parent_node: NodeContainer,
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> None:
        content = resolve_text_without_recursion(template, "<!--", content_ref)
        if content is None or content == "":
            content = ""
        parent_node.children.append(Comment(content))

    def _process_component(
        self,
        parent_node: NodeContainer,
        template: Template,
        last_ctx: ProcessContext,
        attrs: tuple[TAttribute, ...],
        start_i_index: int,
        end_i_index: int | None,
    ) -> None | WalkerProto:
        body_start_s_index = (
            start_i_index
            + 1
            + len([1 for attr in attrs if not isinstance(attr, TLiteralAttribute)])
        )
        start_i = template.interpolations[start_i_index]
        component_callable = start_i.value
        if start_i_index != end_i_index and end_i_index is not None:
            # @TODO: We should do this during parsing.
            children_template = extract_embedded_template(
                template, body_start_s_index, end_i_index
            )
            if component_callable != template.interpolations[end_i_index].value:
                raise TypeError(
                    "Component callable in start tag must match component callable in end tag."
                )
        else:
            children_template = t""

        if not callable(component_callable):
            raise TypeError("Component callable must be callable.")

        kwargs = prep_component_kwargs(
            get_callable_info(component_callable),
            _resolve_t_attrs(attrs, template.interpolations),
            system_kwargs={"children": children_template},
        )

        result_t = component_callable(**kwargs)
        if (
            result_t is not None
            and not isinstance(result_t, Template)
            and callable(result_t)
        ):
            component_obj = cast(ComponentObjectProto, result_t)
            result_t = component_obj()
        else:
            component_obj = None

        if isinstance(result_t, Template):
            if result_t.strings == ("",):
                # DO NOTHING
                return
            result_root = self.parser_api.to_tnode(result_t)
            return self.walk_from_tnode(parent_node, result_t, last_ctx, result_root)
        elif result_t is None:
            # DO NOTHING
            return
        else:
            raise ValueError(f"Unknown component return value: {type(result_t)}")

    def _process_raw_texts(
        self,
        parent_node: NodeContainer,
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> None:
        assert last_ctx.parent_tag in CDATA_CONTENT_ELEMENTS
        content = resolve_text_without_recursion(
            template, last_ctx.parent_tag, content_ref
        )
        if content is None or content == "":
            return
        elif last_ctx.parent_tag == "script":
            parent_node.children.append(
                Text(
                    Markup(
                        self.escape_html_script(
                            content,
                            allow_markup=True,
                        )
                    )
                )
            )
        elif last_ctx.parent_tag == "style":
            parent_node.children.append(
                Text(
                    Markup(
                        self.escape_html_style(
                            content,
                            allow_markup=True,
                        )
                    )
                )
            )
        else:
            raise NotImplementedError(
                f"Parent tag {last_ctx.parent_tag} is not supported."
            )

    def _process_escapable_raw_texts(
        self,
        parent_node: NodeContainer,
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> None:
        assert last_ctx.parent_tag in RCDATA_CONTENT_ELEMENTS
        content = resolve_text_without_recursion(
            template, last_ctx.parent_tag, content_ref
        )
        if content is None or content == "":
            return
        else:
            parent_node.children.append(Text(Markup(self.escape_html_text(content))))

    def _process_normal_text(
        self,
        parent_node: NodeContainer,
        template: Template,
        last_ctx: ProcessContext,
        values_index: int,
    ) -> WalkerProto | None:
        value = format_interpolation(template.interpolations[values_index])
        if isinstance(value, str):
            parent_node.children.append(Text(value))
        elif isinstance(value, Template):
            value_root = self.parser_api.to_tnode(value)
            return self.walk_from_tnode(parent_node, value, last_ctx, value_root)
        elif isinstance(value, Iterable):
            return iter(
                self._process_normal_text_from_value(parent_node, template, last_ctx, v)
                for v in value
            )
        elif value is None:
            # @DESIGN: Ignore None.
            return
        else:
            if isinstance(value, HasHTMLDunder):
                text = Text(Markup(value.__html__()))
            else:
                # @DESIGN: Everything that isn't an object we recognize is
                # coerced to a str() and emitted.
                text = Text(str(value))
            parent_node.children.append(text)

    def _process_normal_text_from_value(
        self,
        parent_node: NodeContainer,
        template: Template,
        last_ctx: ProcessContext,
        value: NormalTextInterpolationValue,
    ) -> WalkerProto | None:
        if isinstance(value, str):
            parent_node.children.append(Text(value))
        elif isinstance(value, Template):
            value_root = self.parser_api.to_tnode(value)
            return self.walk_from_tnode(parent_node, value, last_ctx, value_root)
        elif isinstance(value, Iterable):
            return iter(
                self._process_normal_text_from_value(parent_node, template, last_ctx, v)
                for v in value
            )
        elif value is None:
            # @DESIGN: Ignore None.
            return
        else:
            if isinstance(value, HasHTMLDunder):
                text = Text(Markup(value.__html__()))
            else:
                # @DESIGN: Everything that isn't an object we recognize is
                # coerced to a str() and emitted.
                text = Text(str(value))
            parent_node.children.append(text)


_default_cached_node_processor_api = NodeProcessorService(parser_api=CachedParserService())


def to_node(template: Template, assume_ctx: ProcessContext | None = None) -> Node:
    return _default_cached_node_processor_api.process_template(
        template, assume_ctx=assume_ctx
    )
