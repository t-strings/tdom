import typing as t
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from string.templatelib import Interpolation, Template

from markupsafe import Markup

from .callables import CallableInfo, get_callable_info
from .escaping import (
    escape_html_comment as default_escape_html_comment,
)
from .escaping import (
    escape_html_script as default_escape_html_script,
)
from .escaping import (
    escape_html_style as default_escape_html_style,
)
from .escaping import (
    escape_html_text as default_escape_html_text,
)
from .format import format_interpolation as base_format_interpolation
from .format import format_template
from .htmlspec import (
    CDATA_CONTENT_ELEMENTS,
    DEFAULT_NORMAL_TEXT_ELEMENT,
    RCDATA_CONTENT_ELEMENTS,
    SVG_ATTR_FIX,
    SVG_TAG_FIX,
    VOID_ELEMENTS,
)
from .parser import (
    HTMLAttribute,
    TAttribute,
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TemplateParser,
    TFragment,
    TInterpolatedAttribute,
    TLiteralAttribute,
    TNode,
    TSpreadAttribute,
    TTemplatedAttribute,
    TText,
)
from .protocols import HasHTMLDunder
from .template_utils import TemplateRef
from .utils import CachableTemplate, LastUpdatedOrderedDict

type Attribute = tuple[str, object]
type AttributesDict = dict[str, object]


# --------------------------------------------------------------------------
# Custom formatting for the processor
# --------------------------------------------------------------------------


def _format_safe(value: object, format_spec: str) -> str:
    """Use Markup() to mark a value as safe HTML."""
    assert format_spec == "safe"
    return Markup(value)


def _format_unsafe(value: object, format_spec: str) -> str:
    """Convert a value to a plain string, forcing it to be treated as unsafe."""
    assert format_spec == "unsafe"
    return str(value)


def _format_callback(value: Callable[..., object], format_spec: str) -> object:
    """Execute a callback and return the value."""
    assert format_spec == "callback"
    return value()


CUSTOM_FORMATTERS = (
    ("safe", _format_safe),
    ("unsafe", _format_unsafe),
    ("callback", _format_callback),
)


def format_interpolation(interpolation: Interpolation) -> object:
    return base_format_interpolation(
        interpolation,
        formatters=CUSTOM_FORMATTERS,
    )


# --------------------------------------------------------------------------
# Placeholder Substitution
# --------------------------------------------------------------------------


def _expand_aria_attr(value: object) -> Iterable[HTMLAttribute]:
    """Produce aria-* attributes based on the interpolated value for "aria"."""
    if value is None:
        return
    elif isinstance(value, dict):
        for sub_k, sub_v in value.items():
            if sub_v is True:
                yield f"aria-{sub_k}", "true"
            elif sub_v is False:
                yield f"aria-{sub_k}", "false"
            elif sub_v is None:
                yield f"aria-{sub_k}", None
            else:
                yield f"aria-{sub_k}", str(sub_v)
    else:
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for aria attribute"
        )


def _expand_data_attr(value: object) -> Iterable[Attribute]:
    """Produce data-* attributes based on the interpolated value for "data"."""
    if value is None:
        return
    elif isinstance(value, dict):
        for sub_k, sub_v in value.items():
            if sub_v is True or sub_v is False or sub_v is None:
                yield f"data-{sub_k}", sub_v
            else:
                yield f"data-{sub_k}", str(sub_v)
    else:
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for data attribute"
        )


def _substitute_spread_attrs(value: object) -> Iterable[Attribute]:
    """
    Substitute a spread attribute based on the interpolated value.

    A spread attribute is one where the key is a placeholder, indicating that
    the entire attribute set should be replaced by the interpolated value.
    The value must be a dict or iterable of key-value pairs.
    """
    if value is None:
        return
    elif isinstance(value, dict):
        yield from value.items()
    else:
        raise TypeError(
            f"Cannot use {type(value).__name__} as value for spread attributes"
        )


ATTR_EXPANDERS = {
    "data": _expand_data_attr,
    "aria": _expand_aria_attr,
}


def parse_style_attribute_value(style_str: str) -> list[tuple[str, str | None]]:
    """
    Parse the style declarations out of a style attribute string.
    """
    props = [p.strip() for p in style_str.split(";")]
    styles: list[tuple[str, str | None]] = []
    for prop in props:
        if prop:
            prop_parts = [p.strip() for p in prop.split(":") if p.strip()]
            if len(prop_parts) != 2:
                raise ValueError(
                    f"Invalid number of parts for style property {prop} in {style_str}"
                )
            styles.append((prop_parts[0], prop_parts[1]))
    return styles


def make_style_accumulator(old_value: object) -> StyleAccumulator:
    """
    Initialize the style accumulator.
    """
    match old_value:
        case str():
            styles = {
                name: value for name, value in parse_style_attribute_value(old_value)
            }
        case True:  # A bare attribute will just default to {}.
            styles = {}
        case _:
            raise TypeError(f"Unexpected value: {old_value}")
    return StyleAccumulator(styles=styles)


@dataclass
class StyleAccumulator:
    styles: dict[str, str | None]

    def merge_value(self, value: object) -> None:
        """
        Merge in an interpolated style value.
        """
        match value:
            case str():
                self.styles.update(
                    {name: value for name, value in parse_style_attribute_value(value)}
                )
            case dict():
                self.styles.update(
                    {
                        str(pn): str(pv) if pv is not None else None
                        for pn, pv in value.items()
                    }
                )
            case None:
                pass
            case _:
                raise TypeError(
                    f"Unknown interpolated style value {value}, use '' to omit."
                )

    def to_value(self) -> str | None:
        """
        Serialize the special style value back into a string.

        @NOTE: If the result would be `''` then use `None` to omit the attribute.
        """
        style_value = "; ".join(
            [f"{pn}: {pv}" for pn, pv in self.styles.items() if pv is not None]
        )
        return style_value if style_value else None


def make_class_accumulator(old_value: object) -> ClassAccumulator:
    """
    Initialize the class accumulator.
    """
    match old_value:
        case str():
            toggled_classes = {cn: True for cn in old_value.split()}
        case True:
            toggled_classes = {}
        case _:
            raise ValueError(f"Unexpected value {old_value}")
    return ClassAccumulator(toggled_classes=toggled_classes)


@dataclass
class ClassAccumulator:
    toggled_classes: dict[str, bool]

    def merge_value(self, value: object) -> None:
        """
        Merge in an interpolated class value.
        """
        if isinstance(value, dict):
            self.toggled_classes.update(
                {str(cn): bool(toggle) for cn, toggle in value.items()}
            )
        else:
            if not isinstance(value, str) and isinstance(value, Sequence):
                items = value[:]
            else:
                items = (value,)
            for item in items:
                match item:
                    case str():
                        self.toggled_classes.update({cn: True for cn in item.split()})
                    case None:
                        pass
                    case _:
                        if item == value:
                            raise TypeError(
                                f"Unknown interpolated class value: {value}"
                            )
                        else:
                            raise TypeError(
                                f"Unknown interpolated class item in {value}: {item}"
                            )

    def to_value(self) -> str | None:
        """
        Serialize the special class value back into a string.

        @NOTE: If the result would be `''` then use `None` to omit the attribute.
        """
        class_value = " ".join(
            [cn for cn, toggle in self.toggled_classes.items() if toggle]
        )
        return class_value if class_value else None


ATTR_ACCUMULATOR_MAKERS = {
    "class": make_class_accumulator,
    "style": make_style_accumulator,
}


type AttributeValueAccumulator = StyleAccumulator | ClassAccumulator


def _resolve_t_attrs(
    attrs: Sequence[TAttribute], interpolations: tuple[Interpolation, ...]
) -> AttributesDict:
    """
    Replace placeholder values in attributes with their interpolated values.

    The values returned are not yet processed for HTML output; that is handled
    in a later step.
    """
    new_attrs: AttributesDict = LastUpdatedOrderedDict()
    attr_accs: dict[str, AttributeValueAccumulator] = {}
    for attr in attrs:
        match attr:
            case TLiteralAttribute(name=name, value=value):
                attr_value = True if value is None else value
                if name in ATTR_ACCUMULATOR_MAKERS and name in new_attrs:
                    if name not in attr_accs:
                        attr_accs[name] = ATTR_ACCUMULATOR_MAKERS[name](new_attrs[name])
                    new_attrs[name] = attr_accs[name].merge_value(attr_value)
                else:
                    new_attrs[name] = attr_value
            case TInterpolatedAttribute(name=name, value_i_index=i_index):
                interpolation = interpolations[i_index]
                attr_value = format_interpolation(interpolation)
                if name in ATTR_ACCUMULATOR_MAKERS:
                    if name not in attr_accs:
                        attr_accs[name] = ATTR_ACCUMULATOR_MAKERS[name](
                            new_attrs.get(name, True)
                        )
                    new_attrs[name] = attr_accs[name].merge_value(attr_value)
                elif expander := ATTR_EXPANDERS.get(name):
                    for sub_k, sub_v in expander(attr_value):
                        new_attrs[sub_k] = sub_v
                else:
                    new_attrs[name] = attr_value
            case TTemplatedAttribute(name=name, value_ref=ref):
                attr_t = ref.resolve(interpolations)
                attr_value = format_template(attr_t)
                if name in ATTR_ACCUMULATOR_MAKERS:
                    if name not in attr_accs:
                        attr_accs[name] = ATTR_ACCUMULATOR_MAKERS[name](
                            new_attrs.get(name, True)
                        )
                    new_attrs[name] = attr_accs[name].merge_value(attr_value)
                elif expander := ATTR_EXPANDERS.get(name):
                    raise TypeError(f"{name} attributes cannot be templated")
                else:
                    new_attrs[name] = attr_value
            case TSpreadAttribute(i_index=i_index):
                interpolation = interpolations[i_index]
                spread_value = format_interpolation(interpolation)
                for sub_k, sub_v in _substitute_spread_attrs(spread_value):
                    if sub_k in ATTR_ACCUMULATOR_MAKERS:
                        if sub_k not in attr_accs:
                            attr_accs[sub_k] = ATTR_ACCUMULATOR_MAKERS[sub_k](
                                new_attrs.get(sub_k, True)
                            )
                        new_attrs[sub_k] = attr_accs[sub_k].merge_value(sub_v)
                    elif expander := ATTR_EXPANDERS.get(sub_k):
                        for exp_k, exp_v in expander(sub_v):
                            new_attrs[exp_k] = exp_v
                    else:
                        new_attrs[sub_k] = sub_v
            case _:
                raise ValueError(f"Unknown TAttribute type: {type(attr).__name__}")
    for acc_name, acc in attr_accs.items():
        new_attrs[acc_name] = acc.to_value()
    return new_attrs


def _resolve_html_attrs(attrs: AttributesDict) -> Iterable[HTMLAttribute]:
    """Resolve attribute values for HTML output."""
    for key, value in attrs.items():
        match value:
            case True:
                yield key, None
            case False | None:
                pass
            case _:
                yield key, str(value)


def _kebab_to_snake(name: str) -> str:
    """Convert a kebab-case name to snake_case."""
    return name.replace("-", "_").lower()


def _prep_component_kwargs(
    callable_info: CallableInfo,
    attrs: AttributesDict,
    children: Template,
    provided_attrs: tuple[Attribute, ...] = (),
    raise_on_requires_positional=True,
    raise_on_missing=True,
) -> AttributesDict:
    """
    Matchup kwargs from multiple sources to target the given callable.

    The `provided_attrs` can be used by extensions that want to provide
    kwargs even if they are not specified in a template.
    """

    # We can't know what kwarg to put here...
    if raise_on_requires_positional and callable_info.requires_positional:
        raise TypeError(
            "Component callables cannot have required positional arguments."
        )

    kwargs: AttributesDict = {}

    # Add all supported attributes
    for attr_name, attr_value in attrs.items():
        snake_name = _kebab_to_snake(attr_name)
        if snake_name in callable_info.named_params or callable_info.kwargs:
            kwargs[snake_name] = attr_value

    if "children" in callable_info.named_params or callable_info.kwargs:
        kwargs["children"] = children

    # Add in provided attrs if they haven't been set already and are wanted.
    for pattr_name, pattr_value in provided_attrs:
        if pattr_name not in kwargs and (
            pattr_name in callable_info.named_params or callable_info.kwargs
        ):
            kwargs[pattr_name] = pattr_value

    # Check to make sure we've fully satisfied the callable's requirements
    if raise_on_missing:
        missing = callable_info.required_named_params - kwargs.keys()
        if missing:
            raise TypeError(
                f"Missing required parameters for component: {', '.join(missing)}"
            )

    return kwargs


def serialize_html_attrs(
    html_attrs: Iterable[HTMLAttribute], escape: Callable = default_escape_html_text
) -> str:
    return "".join(
        (f' {k}="{escape(v)}"' if v is not None else f" {k}" for k, v in html_attrs)
    )


def _fix_svg_attrs(html_attrs: Iterable[HTMLAttribute]) -> Iterable[HTMLAttribute]:
    """
    Fix the attr name-case of any html attributes on a tag within an SVG namespace.
    """
    for k, v in html_attrs:
        yield SVG_ATTR_FIX.get(k, k), v


@dataclass(frozen=True, slots=True)
class ProcessContext:
    parent_tag: str = DEFAULT_NORMAL_TEXT_ELEMENT
    ns: str = "html"

    def copy(
        self,
        ns: str | None = None,
        parent_tag: str | None = None,
    ) -> ProcessContext:
        return ProcessContext(
            parent_tag=parent_tag if parent_tag is not None else self.parent_tag,
            ns=ns if ns is not None else self.ns,
        )


type FunctionComponent = Callable[..., Template]
type FactoryComponent = Callable[..., ComponentObject]
type ComponentCallable = FunctionComponent | FactoryComponent
type ComponentObject = Callable[[], Template]


type NormalTextInterpolationValue = (
    None
    | bool  # to support `showValue and value` idiom
    | str
    | HasHTMLDunder
    | Template
    | Iterable[NormalTextInterpolationValue]
    | object
)
# Applies to both escapable raw text and raw text.
type RawTextExactInterpolationValue = (
    None
    | bool  # to support `showValue and value` idiom
    | str
    | HasHTMLDunder
    | object
)
# Applies to both escapable raw text and raw text.
type RawTextInexactInterpolationValue = (
    None
    | bool  # to support `showValue and value` idiom
    | str
    | object
)


class ITemplateParserProxy(t.Protocol):
    def to_tnode(self, template: Template) -> TNode: ...


@dataclass(frozen=True)
class TemplateParserProxy(ITemplateParserProxy):
    def to_tnode(self, template: Template) -> TNode:
        return TemplateParser.parse(template)


@dataclass(frozen=True)
class CachedTemplateParserProxy(TemplateParserProxy):
    @lru_cache(512)  # noqa: B019
    def _to_tnode(self, ct: CachableTemplate) -> TNode:
        return super().to_tnode(ct.template)

    def to_tnode(self, template: Template) -> TNode:
        return self._to_tnode(CachableTemplate(template))


class IComponentProcessor(t.Protocol):
    """Isolate component processing to allow for replacement."""

    def process(
        self,
        template: Template,
        last_ctx: ProcessContext,
        component_callable: t.Annotated[object, ComponentCallable],
        attrs: tuple[TAttribute, ...],
        component_template: Template,
        provided_attrs: tuple[Attribute, ...] = (),
    ) -> tuple[Template, ComponentObject | None]:
        """
        Process available component details into a queryable object or template.
        """
        ...


class ComponentProcessor(IComponentProcessor):
    """
    Default component processor.
    """

    def process(
        self,
        template: Template,
        last_ctx: ProcessContext,
        component_callable: t.Annotated[object, ComponentCallable],
        attrs: tuple[TAttribute, ...],
        component_template: Template,
        provided_attrs: tuple[Attribute, ...] = (),
    ) -> tuple[Template, ComponentObject | None]:
        """
        Process available component details into a queryable object or template.

        Default strategy just uses `_prep_component_kwargs` for `kwargs`
        injecting `children` if asked.
        """
        if not callable(component_callable):
            raise TypeError(
                f"Component callable must be callable: {type(component_callable)}"
            )
        kwargs = _prep_component_kwargs(
            get_callable_info(component_callable),
            _resolve_t_attrs(attrs, template.interpolations),
            children=component_template,
            provided_attrs=provided_attrs,
            raise_on_requires_positional=True,
            raise_on_missing=True,
        )
        res1 = component_callable(**kwargs)  # ty: ignore[call-top-callable]
        # This integration API seems a lot cleaner but we lose the ability for
        # component_object.__call__ to be wrapped in any sort of context setting
        # mechanism provided by the class, but maybe that's ok?  It could be
        # cached on the instance although that is kind of gross.
        if isinstance(res1, Template):
            return res1, None
        elif callable(res1):
            res2 = res1() # ty: ignore[call-top-callable]
            if isinstance(res2, Template):
                # @TODO: It seems like we should not need this.
                # Although our check against res2 doesn't seem to affect the
                # return value of res1.
                return res2, t.cast(ComponentObject, res1)
            else:
                raise TypeError(
                    f"Component object must return Template when called: {type(res2)}"
                )
        else:
            raise TypeError(
                f"Component callable must return Template or Callable: {type(res1)}"
            )


class ITemplateProcessor(t.Protocol):
    def process(self, root_template: Template, assume_ctx: ProcessContext) -> str: ...


@dataclass(frozen=True)
class TemplateProcessor(ITemplateProcessor):
    parser_api: ITemplateParserProxy = field(default_factory=CachedTemplateParserProxy)

    component_processor_api: IComponentProcessor = field(
        default_factory=ComponentProcessor
    )

    escape_html_text: Callable = default_escape_html_text

    escape_html_comment: Callable = default_escape_html_comment

    escape_html_script: Callable = default_escape_html_script

    escape_html_style: Callable = default_escape_html_style

    slash_void: bool = False  # Apply a xhtml-style slash to void html elements.

    uppercase_doctype: bool = False  # DOCTYPE vs doctype

    def process(
        self,
        root_template: Template,
        assume_ctx: ProcessContext,
    ) -> str:
        """
        Process a TDOM compatible template into a string.
        """
        return self._process_template(root_template, assume_ctx)

    def _process_template(self, template: Template, last_ctx: ProcessContext) -> str:
        root = self.parser_api.to_tnode(template)
        return self._process_tnode(template, last_ctx, root)

    def _process_tnode(
        self, template: Template, last_ctx: ProcessContext, tnode: TNode
    ) -> str:
        """
        Process a tnode from a template's "t-tree" into a string.
        """
        match tnode:
            case TDocumentType(text):
                return self._process_document_type(last_ctx, text)
            case TComment(ref):
                return self._process_comment(template, last_ctx, ref)
            case TFragment(children):
                return self._process_fragment(template, last_ctx, children)
            case TComponent(start_i_index, end_i_index, attrs, children):
                return self._process_component(
                    template, last_ctx, attrs, start_i_index, end_i_index
                )
            case TElement(tag, attrs, children):
                return self._process_element(template, last_ctx, tag, attrs, children)
            case TText(ref):
                return self._process_texts(template, last_ctx, ref)
            case _:
                raise ValueError(f"Unrecognized tnode: {tnode}")

    def _process_document_type(
        self,
        last_ctx: ProcessContext,
        text: str,
    ) -> str:
        if last_ctx.ns != "html":
            # Nit
            raise ValueError(
                "Cannot process document type in subtree of a foreign element."
            )
        if self.uppercase_doctype:
            return f"<!DOCTYPE {text}>"
        else:
            return f"<!doctype {text}>"

    def _process_fragment(
        self,
        template: Template,
        last_ctx: ProcessContext,
        children: Iterable[TNode],
    ) -> str:
        return "".join(
            self._process_tnode(template, last_ctx, child) for child in children
        )

    def _process_texts(
        self,
        template: Template,
        last_ctx: ProcessContext,
        ref: TemplateRef,
    ) -> str:
        if last_ctx.parent_tag in CDATA_CONTENT_ELEMENTS:
            # Must be handled all at once.
            return self._process_raw_texts(template, last_ctx, ref)
        elif last_ctx.parent_tag in RCDATA_CONTENT_ELEMENTS:
            # We can handle all at once because there are no non-text children and everything must be string-ified.
            return self._process_escapable_raw_texts(template, last_ctx, ref)
        else:
            return self._process_normal_texts(template, last_ctx, ref)

    def _process_comment(
        self,
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> str:
        """
        Process a comment into a string.
        """
        content_str = resolve_text_without_recursion(template, "<!--", content_ref)
        escaped_comment_str = self.escape_html_comment(content_str, allow_markup=True)
        return f"<!--{escaped_comment_str}-->"

    def _process_element(
        self,
        template: Template,
        last_ctx: ProcessContext,
        tag: str,
        attrs: tuple[TAttribute, ...],
        children: tuple[TNode, ...],
    ) -> str:
        out: list[str] = []
        if tag == "svg":
            our_ctx = last_ctx.copy(parent_tag=tag, ns="svg")
        elif tag == "math":
            our_ctx = last_ctx.copy(parent_tag=tag, ns="math")
        else:
            our_ctx = last_ctx.copy(parent_tag=tag)
        if our_ctx.ns == "svg":
            starttag = endtag = SVG_TAG_FIX.get(tag, tag)
        else:
            starttag = endtag = tag
        out.append(f"<{starttag}")
        if attrs:
            out.append(self._process_attrs(template, our_ctx, attrs))
        # @TODO: How can we tell if we write out children or not in
        # order to self-close in non-html contexts, ie. SVG?
        if self.slash_void and tag in VOID_ELEMENTS:
            out.append(" />")
        else:
            out.append(">")
        if tag not in VOID_ELEMENTS:
            # We were still in SVG but now we default back into HTML
            if tag == "foreignobject":
                child_ctx = our_ctx.copy(ns="html")
            else:
                child_ctx = our_ctx
            out.extend(
                self._process_tnode(template, child_ctx, child) for child in children
            )
            out.append(f"</{endtag}>")
        return "".join(out)

    def _process_attrs(
        self,
        template: Template,
        last_ctx: ProcessContext,
        attrs: tuple[TAttribute, ...],
    ) -> str:
        """
        Process an element's attributes into a string.
        """
        resolved_attrs = _resolve_t_attrs(attrs, template.interpolations)
        if last_ctx.ns == "svg":
            attrs_str = serialize_html_attrs(
                _fix_svg_attrs(_resolve_html_attrs(resolved_attrs))
            )
        else:
            attrs_str = serialize_html_attrs(_resolve_html_attrs(resolved_attrs))
        if attrs_str:
            return attrs_str
        return ""

    def _extract_component_template(
        self,
        template: Template,
        attrs: tuple[TAttribute, ...],
        start_i_index: int,
        end_i_index: int | None,
        check_callables: bool = True,
    ) -> Template:
        body_start_s_index = (
            start_i_index
            + 1
            + len([1 for attr in attrs if not isinstance(attr, TLiteralAttribute)])
        )
        if start_i_index != end_i_index and end_i_index is not None:
            # @TODO: We should do this during parsing.
            if (
                check_callables
                and template.interpolations[start_i_index].value
                != template.interpolations[end_i_index].value
            ):
                raise TypeError(
                    "Component callable in start tag must match component callable in end tag."
                )
            return extract_embedded_template(template, body_start_s_index, end_i_index)
        else:
            return t""

    def _process_component(
        self,
        template: Template,
        last_ctx: ProcessContext,
        attrs: tuple[TAttribute, ...],
        start_i_index: int,
        end_i_index: int | None,
    ) -> str:
        """
        Invoke a component and process the result into a string.
        """
        children_template = self._extract_component_template(
            template, attrs, start_i_index, end_i_index, check_callables=True
        )
        component_callable = template.interpolations[start_i_index].value
        result_t, component_object = self.component_processor_api.process(
            template, last_ctx, component_callable, attrs, children_template
        )
        assert isinstance(component_object, object)
        return self._process_template(result_t, last_ctx)

    def _process_raw_texts(
        self,
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> str:
        """
        Process the given content into a string as "raw text".
        """
        assert last_ctx.parent_tag in CDATA_CONTENT_ELEMENTS
        content = resolve_text_without_recursion(
            template, last_ctx.parent_tag, content_ref
        )
        if last_ctx.parent_tag == "script":
            return self.escape_html_script(
                content,
                allow_markup=True,
            )
        elif last_ctx.parent_tag == "style":
            return self.escape_html_style(
                content,
                allow_markup=True,
            )
        else:
            raise NotImplementedError(
                f"Parent tag {last_ctx.parent_tag} is not supported."
            )

    def _process_escapable_raw_texts(
        self,
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> str:
        """
        Process the given content into a string as "escapable raw text".
        """
        assert last_ctx.parent_tag in RCDATA_CONTENT_ELEMENTS
        content = resolve_text_without_recursion(
            template, last_ctx.parent_tag, content_ref
        )
        return self.escape_html_text(content)

    def _process_normal_texts(
        self, template: Template, last_ctx: ProcessContext, content_ref: TemplateRef
    ):
        """
        Process the given context into a string as "normal text".
        """
        return "".join(
            (
                self.escape_html_text(part)
                if isinstance(part, str)
                else self._process_normal_text(template, last_ctx, t.cast(int, part))
            )
            for part in content_ref
        )

    def _process_normal_text(
        self,
        template: Template,
        last_ctx: ProcessContext,
        values_index: int,
    ) -> str:
        """
        Process the value of the interpolation into a string as "normal text".

        @NOTE: This is an interpolation that must be formatted to get the value.
        """
        value = format_interpolation(template.interpolations[values_index])
        value = t.cast(NormalTextInterpolationValue, value)  # ty: ignore[redundant-cast]
        return self._process_normal_text_from_value(template, last_ctx, value)

    def _process_normal_text_from_value(
        self,
        template: Template,
        last_ctx: ProcessContext,
        value: NormalTextInterpolationValue,
    ) -> str:
        """
        Process a single value into a string as "normal text".

        @NOTE: This is an actual value and NOT an interpolation.  This is meant to be
        used when processing an iterable of values as normal text.
        """
        if value is None or isinstance(value, bool):
            return ""
        elif isinstance(value, str):
            # @NOTE: This would apply to Markup() but not to a custom object
            # implementing HasHTMLDunder.
            return self.escape_html_text(value)
        elif isinstance(value, Template):
            return self._process_template(value, last_ctx)
        elif isinstance(value, Iterable):
            return "".join(
                self._process_normal_text_from_value(template, last_ctx, v)
                for v in value
            )
        elif isinstance(value, HasHTMLDunder):
            # @NOTE: markupsafe's escape does this for us but we put this in
            # here for completeness.
            # @NOTE: An actual Markup() would actually pass as a str() but a
            # custom object with __html__ might not.
            return Markup(value.__html__())
        else:
            # @DESIGN: Everything that isn't an object we recognize is
            # coerced to a str() and emitted.
            return self.escape_html_text(value)


def resolve_text_without_recursion(
    template: Template, parent_tag: str, content_ref: TemplateRef
) -> str:
    """
    Resolve the text in the given template without recursing into more structured text.

    This can be bypassed by interpolating an exact match with an object with `__html__()`.

    A non-exact match is not allowed because we cannot process escaping
    across the boundary between other content and the pass-through content.
    """
    if content_ref.is_singleton:
        value = format_interpolation(template.interpolations[content_ref.i_indexes[0]])
        value = t.cast(RawTextExactInterpolationValue, value)  # ty: ignore[redundant-cast]
        if value is None or isinstance(value, bool):
            return ""
        elif isinstance(value, str):
            return value
        elif isinstance(value, HasHTMLDunder):
            # @DESIGN: We could also force callers to use `:safe` to trigger
            # the interpolation in this special case.
            return Markup(value.__html__())
        elif isinstance(value, (Template, Iterable)):
            raise ValueError(
                f"Recursive includes are not supported within {parent_tag}"
            )
        else:
            return str(value)
    else:
        text = []
        for part in content_ref:
            if isinstance(part, str):
                if part:
                    text.append(part)
                continue
            value = format_interpolation(template.interpolations[part])
            value = t.cast(RawTextInexactInterpolationValue, value)  # ty: ignore[redundant-cast]
            if value is None or isinstance(value, bool):
                continue
            elif (
                type(value) is str
            ):  # type() check to avoid subclasses, probably something smarter here
                if value:
                    text.append(value)
            elif not isinstance(value, str) and isinstance(value, (Template, Iterable)):
                raise ValueError(
                    f"Recursive includes are not supported within {parent_tag}"
                )
            elif isinstance(value, HasHTMLDunder):
                raise ValueError(
                    f"Non-exact trusted interpolations are not supported within {parent_tag}"
                )
            else:
                value_str = str(value)
                if value_str:
                    text.append(value_str)
        return "".join(text)


def extract_embedded_template(
    template: Template, body_start_s_index: int, end_i_index: int
) -> Template:
    """
    Extract the template parts exclusively from start tag to end tag.

    Note that interpolations INSIDE the start tag make this more complex
    than just "the `s_index` after the component callable's `i_index`".

    Example:
    ```python
    template = (
        t'<{comp} attr={attr}>'
            t'<div>{content} <span>{footer}</span></div>'
        t'</{comp}>'
    )
    assert extract_children_template(template, 2, 4) == (
        t'<div>{content} <span>{footer}</span></div>'
    )
    starttag = t'<{comp} attr={attr}>'
    endtag = t'</{comp}>'
    assert template == starttag + extract_children_template(template, 2, 4) + endtag
    ```
    @DESIGN: "There must be a better way."
    """
    # Copy the parts out of the containing template.
    index = body_start_s_index
    last_s_index = end_i_index
    parts = []
    while index <= last_s_index:
        parts.append(template.strings[index])
        if index != last_s_index:
            parts.append(template.interpolations[index])
        index += 1
    # Now trim the first part to the end of the opening tag.
    parts[0] = parts[0][parts[0].find(">") + 1 :]
    # Now trim the last part (could also be the first) to the start of the closing tag.
    parts[-1] = parts[-1][: parts[-1].rfind("<")]
    return Template(*parts)


def _make_default_template_processor(
    parser_api: ITemplateParserProxy | None = None,
) -> ITemplateProcessor:
    """
    Wrap our default options but allow parser api to change for testing.
    """
    return TemplateProcessor(
        parser_api=CachedTemplateParserProxy() if parser_api is None else parser_api,
        slash_void=True,
        uppercase_doctype=True,
    )


_default_template_processor_api: ITemplateProcessor = _make_default_template_processor()


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def html(template: Template, assume_ctx: ProcessContext | None = None) -> str:
    """Parse an HTML t-string, substitute values, and return a string of HTML."""
    if assume_ctx is None:
        assume_ctx = ProcessContext()
    return _default_template_processor_api.process(template, assume_ctx)


def svg(template: Template, assume_ctx: ProcessContext | None = None) -> str:
    """Parse a standalone SVG fragment and return a string of HTML.

    Use when the template does not contain an ``<svg>`` wrapper element.
    Tag and attribute case-fixing (e.g. ``clipPath``, ``viewBox``) are applied
    from the root, exactly as they would be inside ``html(t"<svg>...</svg>")``.

    When the template does contain ``<svg>``, use ``html()`` — the SVG context
    is detected automatically.
    """
    if assume_ctx is None:
        assume_ctx = ProcessContext(ns="svg")
    return html(template, assume_ctx=assume_ctx)
