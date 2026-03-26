from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from string.templatelib import Interpolation, Template
from typing import cast

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
    VOID_ELEMENTS,
)
from .parser import (
    HTMLAttribute,
    HTMLAttributesDict,
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
from .sentinel import NOT_SET, NotSet
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


def _resolve_html_attrs(attrs: AttributesDict) -> HTMLAttributesDict:
    """Resolve attribute values for HTML output."""
    html_attrs: HTMLAttributesDict = {}
    for key, value in attrs.items():
        match value:
            case True:
                html_attrs[key] = None
            case False | None:
                pass
            case _:
                html_attrs[key] = str(value)
    return html_attrs


def _kebab_to_snake(name: str) -> str:
    """Convert a kebab-case name to snake_case."""
    return name.replace("-", "_").lower()


def prep_component_kwargs(
    callable_info: CallableInfo,
    attrs: AttributesDict,
    system_kwargs: AttributesDict,
) -> AttributesDict:
    if callable_info.requires_positional:
        raise TypeError(
            "Component callables cannot have required positional arguments."
        )

    kwargs: AttributesDict = {}

    # Add all supported attributes
    for attr_name, attr_value in attrs.items():
        snake_name = _kebab_to_snake(attr_name)
        if snake_name in callable_info.named_params or callable_info.kwargs:
            kwargs[snake_name] = attr_value

    for attr_name, attr_value in system_kwargs.items():
        if attr_name in callable_info.named_params or callable_info.kwargs:
            kwargs[attr_name] = attr_value

    # Check to make sure we've fully satisfied the callable's requirements
    missing = callable_info.required_named_params - kwargs.keys()
    if missing:
        raise TypeError(
            f"Missing required parameters for component: {', '.join(missing)}"
        )

    return kwargs


@dataclass
class EndTag:
    end_tag: str


def serialize_html_attrs(
    html_attrs: HTMLAttributesDict, escape: Callable = default_escape_html_text
) -> str:
    return "".join(
        (
            f' {k}="{escape(v)}"' if v is not None else f" {k}"
            for k, v in html_attrs.items()
        )
    )


def make_ctx(parent_tag: str | None = None, ns: str | None = "html"):
    return ProcessContext(parent_tag=parent_tag, ns=ns)


@dataclass(frozen=True, slots=True)
class ProcessContext:
    # None means unknown not just a missing value.
    parent_tag: str | None = None
    # None means unknown not just a missing value.
    ns: str | None = None

    def copy(
        self,
        ns: NotSet | str | None = NOT_SET,
        parent_tag: NotSet | str | None = NOT_SET,
    ):
        if isinstance(ns, NotSet):
            resolved_ns = self.ns
        else:
            resolved_ns = ns
        if isinstance(parent_tag, NotSet):
            resolved_parent_tag = self.parent_tag
        else:
            resolved_parent_tag = parent_tag
        return make_ctx(
            parent_tag=resolved_parent_tag,
            ns=resolved_ns,
        )


type FunctionComponentProto = Callable[..., Template]
type FactoryComponentProto = Callable[..., ComponentObjectProto]
type ComponentCallableProto = FunctionComponentProto | FactoryComponentProto
type ComponentObjectProto = Callable[[], Template]


type WalkerProto = Iterable[WalkerProto | None]


type NormalTextInterpolationValue = (
    None | str | Template | Iterable[NormalTextInterpolationValue] | object
)
# Applies to both escapable raw text and raw text.
type RawTextExactInterpolationValue = None | str | HasHTMLDunder | object
# Applies to both escapable raw text and raw text.
type RawTextInexactInterpolationValue = None | str | object


@dataclass(frozen=True)
class ParserService:
    svg_context: bool = False

    def to_tnode(self, template: Template) -> TNode:
        return TemplateParser.parse(template, svg_context=self.svg_context)


@dataclass(frozen=True)
class CachedParserService(ParserService):
    @lru_cache(512)  # noqa: B019
    def _to_tnode(self, ct: CachableTemplate):
        return super().to_tnode(ct.template)

    def to_tnode(self, template: Template):
        return self._to_tnode(CachableTemplate(template))


@dataclass(frozen=True)
class BaseProcessorService:
    parser_api: ParserService

    escape_html_text: Callable = default_escape_html_text

    escape_html_comment: Callable = default_escape_html_comment

    escape_html_script: Callable = default_escape_html_script

    escape_html_style: Callable = default_escape_html_style


@dataclass(frozen=True)
class ProcessorService(BaseProcessorService):
    slash_void: bool = False  # Apply a xhtml-style slash to void html elements.

    uppercase_doctype: bool = False  # DOCTYPE vs doctype

    def process_template(
        self, root_template: Template, assume_ctx: ProcessContext | None = None
    ) -> str:
        return "".join(self.process_template_chunks(root_template, assume_ctx))

    def process_template_chunks(
        self, root_template: Template, assume_ctx: ProcessContext | None = None
    ) -> Iterable[str]:
        if assume_ctx is None:
            # @DESIGN: What do we want to do here?  Should we assume we are in
            # a tag with normal text?
            assume_ctx = make_ctx(parent_tag=DEFAULT_NORMAL_TEXT_ELEMENT, ns="html")
        root = self.parser_api.to_tnode(root_template)

        bf: list[str] = []
        q: list[WalkerProto] = [
            self.walk_from_tnode(bf, root_template, assume_ctx, root)
        ]
        while q:
            it = q.pop()
            if bf:
                yield "".join(bf)
                bf.clear()
            for new_it in it:
                if new_it is not None:
                    q.append(it)
                    q.append(new_it)
                    break
        if bf:
            yield "".join(bf)
            bf.clear()  # Remove later maybe.

    def walk_from_tnode(
        self, bf: list[str], template: Template, assume_ctx: ProcessContext, root: TNode
    ) -> Iterable[WalkerProto]:
        """
        Walk around tree and try not to get lost.
        """

        q: list[tuple[ProcessContext, TNode | EndTag]] = [(assume_ctx, root)]
        while q:
            last_ctx, tnode = q.pop()
            match tnode:
                case EndTag(end_tag):
                    bf.append(end_tag)
                case TDocumentType(text):
                    if last_ctx.ns != "html":
                        # Nit
                        raise ValueError(
                            "Cannot process document type in subtree of a foreign element."
                        )
                    if self.uppercase_doctype:
                        bf.append(f"<!DOCTYPE {text}>")
                    else:
                        bf.append(f"<!doctype {text}>")
                case TComment(ref):
                    self._process_comment(bf, template, last_ctx, ref)
                case TFragment(children):
                    q.extend([(last_ctx, child) for child in reversed(children)])
                case TComponent(start_i_index, end_i_index, attrs, children):
                    res = self._process_component(
                        bf, template, last_ctx, attrs, start_i_index, end_i_index
                    )
                    if res is not None:
                        yield res
                case TElement(tag, attrs, children):
                    bf.append(f"<{tag}")
                    our_ctx = last_ctx.copy(parent_tag=tag)
                    if attrs:
                        self._process_attrs(bf, template, our_ctx, attrs)
                    # @TODO: How can we tell if we write out children or not in
                    # order to self-close in non-html contexts, ie. SVG?
                    if self.slash_void and tag in VOID_ELEMENTS:
                        bf.append(" />")
                    else:
                        bf.append(">")
                    if tag not in VOID_ELEMENTS:
                        q.append((last_ctx, EndTag(f"</{tag}>")))
                        q.extend([(our_ctx, child) for child in reversed(children)])
                case TText(ref):
                    if last_ctx.parent_tag is None:
                        raise NotImplementedError(
                            "We cannot interpolate texts without knowing what tag they are contained in."
                        )
                    elif last_ctx.parent_tag in CDATA_CONTENT_ELEMENTS:
                        # Must be handled all at once.
                        self._process_raw_texts(bf, template, last_ctx, ref)
                    elif last_ctx.parent_tag in RCDATA_CONTENT_ELEMENTS:
                        # We can handle all at once because there are no non-text children and everything must be string-ified.
                        self._process_escapable_raw_texts(bf, template, last_ctx, ref)
                    else:
                        for part in ref:
                            if isinstance(part, str):
                                bf.append(self.escape_html_text(part))
                            else:
                                res = self._process_normal_text(
                                    bf, template, last_ctx, part
                                )
                                if res is not None:
                                    yield res
                case _:
                    raise ValueError(f"Unrecognized tnode: {tnode}")

    def _process_comment(
        self,
        bf: list[str],
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> None:
        content = resolve_text_without_recursion(template, "<!--", content_ref)
        bf.append("<!--")
        if content is None or content == "":
            pass
        else:
            bf.append(
                self.escape_html_comment(
                    content,
                    allow_markup=True,
                )
            )
        bf.append("-->")

    def _process_attrs(
        self,
        bf: list[str],
        template: Template,
        last_ctx: ProcessContext,
        attrs: tuple[TAttribute, ...],
    ) -> None:
        resolved_attrs = _resolve_t_attrs(attrs, template.interpolations)
        attrs_str = serialize_html_attrs(_resolve_html_attrs(resolved_attrs))
        if attrs_str:
            bf.append(attrs_str)

    def _process_component(
        self,
        bf: list[str],
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
        component_callable = cast(ComponentCallableProto, start_i.value)
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
            component_obj = result_t
            result_t = component_obj()
        else:
            component_obj = None

        if isinstance(result_t, Template):
            if result_t.strings == ("",):
                # DO NOTHING
                return
            result_root = self.parser_api.to_tnode(result_t)
            return self.walk_from_tnode(bf, result_t, last_ctx, result_root)
        else:
            raise TypeError(f"Unknown component return value: {type(result_t)}")

    def _process_raw_texts(
        self,
        bf: list[str],
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
            bf.append(
                self.escape_html_script(
                    content,
                    allow_markup=True,
                )
            )
        elif last_ctx.parent_tag == "style":
            bf.append(
                self.escape_html_style(
                    content,
                    allow_markup=True,
                )
            )
        else:
            raise NotImplementedError(
                f"Parent tag {last_ctx.parent_tag} is not supported."
            )

    def _process_escapable_raw_texts(
        self,
        bf: list[str],
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
            bf.append(
                self.escape_html_text(
                    content,
                )
            )

    def _process_normal_text(
        self,
        bf: list[str],
        template: Template,
        last_ctx: ProcessContext,
        values_index: int,
    ) -> WalkerProto | None:
        value = format_interpolation(template.interpolations[values_index])
        if isinstance(value, str):
            bf.append(self.escape_html_text(value))
        elif isinstance(value, Template):
            value_root = self.parser_api.to_tnode(value)
            return self.walk_from_tnode(bf, value, last_ctx, value_root)
        elif isinstance(value, Iterable):
            return iter(
                self._process_normal_text_from_value(bf, template, last_ctx, v)
                for v in value
            )
        elif value is None:
            # @DESIGN: Ignore None.
            return
        else:
            # @DESIGN: Everything that isn't an object we recognize is
            # coerced to a str() and emitted.
            bf.append(self.escape_html_text(value))

    def _process_normal_text_from_value(
        self,
        bf: list[str],
        template: Template,
        last_ctx: ProcessContext,
        value: NormalTextInterpolationValue,
    ) -> WalkerProto | None:
        if isinstance(value, str):
            bf.append(self.escape_html_text(value))
        elif isinstance(value, Template):
            value_root = self.parser_api.to_tnode(value)
            return self.walk_from_tnode(bf, value, last_ctx, value_root)
        elif isinstance(value, Iterable):
            return iter(
                self._process_normal_text_from_value(bf, template, last_ctx, v)
                for v in value
            )
        elif value is None:
            # @DESIGN: Ignore None.
            return
        else:
            # @DESIGN: Everything that isn't an object we recognize is
            # coerced to a str() and emitted.
            bf.append(self.escape_html_text(value))


def resolve_text_without_recursion(
    template: Template, parent_tag: str, content_ref: TemplateRef
) -> str | None:
    """
    Resolve the text in the given template without recursing into more structured text.

    This can be bypassed by interpolating an exact match with an object with `__html__()`.

    A non-exact match is not allowed because we cannot process escaping
    across the boundary between other content and the pass-through content.
    """
    if content_ref.is_singleton:
        value = format_interpolation(template.interpolations[content_ref.i_indexes[0]])
        if value is None:
            return None
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
            if value is None:
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
        if text:
            return "".join(text)
        else:
            return None


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


def processor_service_factory(**config_kwargs):
    return ProcessorService(parser_api=ParserService(), **config_kwargs)


def cached_processor_service_factory(**config_kwargs):
    return ProcessorService(parser_api=CachedParserService(), **config_kwargs)


def svg_processor_service_factory(**config_kwargs):
    return ProcessorService(parser_api=ParserService(svg_context=True), **config_kwargs)


def cached_svg_processor_service_factory(**config_kwargs):
    return ProcessorService(
        parser_api=CachedParserService(svg_context=True), **config_kwargs
    )


_default_processor_api = cached_processor_service_factory(
    slash_void=True, uppercase_doctype=True
)

_default_svg_processor_api = cached_svg_processor_service_factory(
    slash_void=True, uppercase_doctype=True
)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def to_html(template: Template, assume_ctx: ProcessContext | None = None) -> str:
    """Parse an HTML t-string, substitute values, and return a string of HTML."""
    return _default_processor_api.process_template(template, assume_ctx)


def to_svg(template: Template) -> str:
    """Parse a standalone SVG fragment and return a tree of Nodes.

    Use when the template does not contain an ``<svg>`` wrapper element.
    Tag and attribute case-fixing (e.g. ``clipPath``, ``viewBox``) are applied
    from the root, exactly as they would be inside ``html(t"<svg>...</svg>")``.

    When the template does contain ``<svg>``, use ``html()`` — the SVG context
    is detected automatically.
    """
    return _default_svg_processor_api.process_template(template, make_ctx(ns="svg"))
