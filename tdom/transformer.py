from dataclasses import dataclass
from string.templatelib import Interpolation, Template
from typing import Callable
from collections.abc import Iterable, Sequence
import typing as t
from contextlib import nullcontext
from contextvars import ContextVar, Token
import functools
from markupsafe import Markup

from .format import format_interpolation
from .parser import TemplateParser, HTMLAttributesDict
from .tnodes import (
    TNode,
    TFragment,
    TElement,
    TText,
    TDocumentType,
    TComment,
    TComponent,
    TLiteralAttribute,
    TAttribute,
)
from .nodes import (
    VOID_ELEMENTS,
    CDATA_CONTENT_ELEMENTS,
    RCDATA_CONTENT_ELEMENTS,
)
from .escaping import (
    escape_html_content_in_tag as default_escape_html_content_in_tag,
    escape_html_text as default_escape_html_text,
    escape_html_comment as default_escape_html_comment,
)
from .utils import CachableTemplate
from .processor import (
    _resolve_t_attrs as resolve_dynamic_attrs,
    _resolve_html_attrs as coerce_to_html_attrs,
    _kebab_to_snake,
    HasHTMLDunder,
    AttributesDict,
)
from .callables import get_callable_info


@dataclass
class EndTag:
    end_tag: str


def render_html_attrs(
    html_attrs: HTMLAttributesDict, escape: Callable = default_escape_html_text
) -> str:
    return "".join(
        (
            f' {k}="{escape(v)}"' if v is not None else f" {k}"
            for k, v in html_attrs.items()
        )
    )


type InterpolateInfo = tuple


type RenderQueueItem = tuple[
    str | None, t.Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]]
]


class InterpolatorProto(t.Protocol):
    def __call__(
        self,
        render_api: RenderService,
        bf: list[str],
        last_container_tag: str | None,
        template: Template,
        ip_info: InterpolateInfo,
    ) -> RenderQueueItem | None:
        """
        Populates an interpolation or returns iterator to decende into.

        If recursion is required then pushes current iterator.

        render_api
            The current render api, provides various helper methods to the interpolator.
        bf
            A list-like output buffer.
        last_container_tag
            The last HTML tag known for this interpolation, this cannot always be 100% accurate.
        template
            The "values" template that is being used to fulfill interpolations.
        ip_info
            The information provided in the structured template interpolation OR from another source,
            for example a value from a user provided iterator.

        Returns a render queue item when the main iteration loops needs to be paused and restarted to descend.
        """
        raise NotImplementedError


type InterpolateCommentInfo = tuple[str, Template]


def interpolate_comment(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    container_tag, comment_t = t.cast(InterpolateCommentInfo, ip_info)
    assert container_tag == "<!--"
    bf.append(
        render_api.escape_html_comment(
            render_api.resolve_text_without_recursion(
                template, container_tag, comment_t
            )
        )
    )


type InterpolateAttrsInfo = tuple[str, Sequence[TAttribute]]


def interpolate_attrs(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    container_tag, attrs = t.cast(InterpolateAttrsInfo, ip_info)
    resolved_attrs = render_api.resolve_attrs(attrs, template)
    attrs_str = render_html_attrs(coerce_to_html_attrs(resolved_attrs))
    bf.append(attrs_str)


def _prep_cinfo(
    component_callable: Callable, attrs: AttributesDict, system: dict[str, object]
):
    # @DESIGN: This is lifted from the processor and then grossified.
    # Not sure this will work out but maybe we'd unify these.
    callable_info = get_callable_info(component_callable)

    if callable_info.requires_positional:
        raise TypeError(
            "Component callables cannot have required positional arguments."
        )

    kwargs: AttributesDict = {}

    # Inject system kwargs first.
    if system:
        if callable_info.kwargs:
            kwargs.update(system)
        else:
            for kw in system:
                if kw in callable_info.named_params:
                    kwargs[kw] = system[kw]

    # Plaster attributes in over top of system kwargs.
    for attr_name, attr_value in attrs.items():
        snake_name = _kebab_to_snake(attr_name)
        if snake_name in callable_info.named_params or callable_info.kwargs:
            kwargs[snake_name] = attr_value

    # Check to make sure we've fully satisfied the callable's requirements
    missing = callable_info.required_named_params - kwargs.keys()
    if missing:
        raise TypeError(
            f"Missing required parameters for component: {', '.join(missing)}"
        )

    return kwargs


type InterpolateComponentInfo = tuple[str, Sequence[TAttribute], int, int | None, int]


def interpolate_component(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    (container_tag, attrs, start_i_index, end_i_index, body_start_s_index) = t.cast(
        InterpolateComponentInfo, ip_info
    )
    if start_i_index != end_i_index and end_i_index is not None:
        # @DESIGN: We extract the children template from the original outer template.
        children_template = render_api.transform_api.extract_children_template(
            template, body_start_s_index, end_i_index
        )
    else:
        children_template = Template("")
    # @DESIGN: children_struct_t = render_api.transform_api.transform_template(children_template) ?
    resolved_attrs = render_api.resolve_attrs(attrs, template)
    start_i = template.interpolations[start_i_index]
    component_callable = start_i.value
    if (
        start_i_index != end_i_index
        and end_i_index is not None
        and component_callable != template.interpolations[end_i_index].value
    ):
        raise TypeError(
            "Component callable in start tag must match component callable in end tag."
        )

    # @DESIGN: Inject system vars via manager?
    system_dict = render_api.get_system(
        children=children_template  # @DESIGN: children_struct=children_struct_t ?
    )
    # @DESIGN: Determine return signature from callable info (cached inspection) ?
    kwargs = _prep_cinfo(component_callable, resolved_attrs, system_dict)
    res = component_callable(**kwargs)
    # @DESIGN: Determine return signature via runtime inspection?
    if isinstance(res, tuple):
        result_template, comp_info = res
        context_values = comp_info.get("context_values", ()) if comp_info else ()
    else:
        result_template = res
        comp_info = None
        context_values = ()

    # @DESIGN: Use open-ended dict for opt-in second return argument?
    context_values = comp_info.get("context_values", ()) if comp_info else ()

    if result_template:
        result_struct = render_api.transform_api.transform_template(result_template)
        if context_values:
            walker = render_api.walk_template_with_context(
                bf, result_template, result_struct, context_values=context_values
            )
        else:
            walker = render_api.walk_template(bf, result_template, result_struct)
        return (container_tag, iter(walker))


type InterpolateRawTextInfo = tuple[str, Template]


def interpolate_raw_text(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    container_tag, content_t = t.cast(InterpolateRawTextInfo, ip_info)
    bf.append(
        render_api.escape_html_content_in_tag(
            container_tag,
            render_api.resolve_text_without_recursion(
                template, container_tag, content_t
            ),
        )
    )


type InterpolateEscapableRawTextInfo = tuple[str, Template]


def interpolate_escapable_raw_text(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    container_tag, content_t = t.cast(InterpolateEscapableRawTextInfo, ip_info)
    bf.append(
        render_api.escape_html_text(
            render_api.resolve_text_without_recursion(
                template, container_tag, content_t
            )
        )
    )


type InterpolateStructTextInfo = tuple[str, int]


def interpolate_struct_text(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    container_tag, ip_index = t.cast(InterpolateStructTextInfo, ip_info)
    value = format_interpolation(template.interpolations[ip_index])
    return interpolate_text(
        render_api, bf, last_container_tag, template, (container_tag, value)
    )


# @TODO: can we coerce this to still use typing even if we just str() everything ? -- `| object`
type UserTextValueItem = None | str | Template | HasHTMLDunder
# @TODO: See above about `| object`
type UserTextValue = (
    UserTextValueItem | Sequence[UserTextValueItem] | t.Iterable[UserTextValueItem]
)


def interpolate_user_text(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    return interpolate_text(render_api, bf, last_container_tag, template, ip_info)


type InterpolateTextInfo = tuple[str, object]


def interpolate_text(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    container_tag, value = t.cast(InterpolateTextInfo, ip_info)
    if container_tag is None:
        container_tag = last_container_tag

    #
    # Try to optimize past this block if the value is a str.
    #
    if not isinstance(value, str):
        if isinstance(value, Template):
            return (
                container_tag,
                iter(
                    render_api.walk_template(
                        bf, value, render_api.transform_api.transform_template(value)
                    )
                ),
            )
        elif isinstance(value, t.Sequence) or hasattr(value, "__iter__"):
            return (
                # yield (populate, template, value)
                container_tag,
                (
                    (
                        interpolate_user_text,
                        template,
                        (container_tag, v if v is not None else None),
                    )
                    for v in t.cast(Iterable, value)
                ),
            )
        elif value is False or value is None:
            # Do nothing here, we don't even need to yield ''.
            return
        else:
            # Fall's through, we should rewrite this.
            pass

    if container_tag not in ("style", "script", "title", "textarea", "<!--"):
        if hasattr(value, "__html__"):
            value = t.cast(HasHTMLDunder, value)
            bf.append(value.__html__())
        else:
            bf.append(render_api.escape_html_text(value))
    else:
        # @TODO: How could this happen?
        raise ValueError(
            f"We cannot escape text within {container_tag} when multiple interpolations could occur."
        )
        # bf.append(render_api.escape_html_content_in_tag(container_tag, str(value)))


@dataclass(frozen=True)
class TransformService:
    """
    Turn a structure node tree into an optimized Template that can be quickly interpolated into a string.

    - Tag attributes with any interpolations are replaced with a single interpolation.
    - Component invocations are replaced with a single interpolation.
    - Runs of strings are consolidated around or in between interpolations.
      If there are no strings provided to build a proper template then empty strings are injected.
    """

    escape_html_text: Callable = default_escape_html_text

    slash_void: bool = False  # Apply a xhtml-style slash to void html elements.

    def transform_template(self, template: Template) -> Template:
        """Transform the given template into a template for rendering."""
        struct_node = self.to_struct_node(template)
        return self.to_struct_template(struct_node)

    def to_struct_node(self, template: Template) -> TNode:
        return TemplateParser.parse(template)

    def to_struct_template(self, struct_node: TNode) -> Template:
        """Recombine stream of tokens from node trees into a new template."""
        return Template(*self.streamer(struct_node))

    def _stream_comment_interpolation(self, text_t: Template):
        info = ("<!--", text_t)
        return Interpolation(
            (interpolate_comment, info), "", None, "html_comment_template"
        )

    def _stream_attrs_interpolation(
        self, last_container_tag: str | None, attrs: t.Sequence[TAttribute]
    ):
        info = (last_container_tag, attrs)
        return Interpolation((interpolate_attrs, info), "", None, "html_attrs_seq")

    def _stream_component_interpolation(
        self, last_container_tag, attrs, start_i_index, end_i_index
    ):
        # If the interpolation is at 1, then the opening string starts inside at least string 2 (+1)
        # but it can't start until after any dynamic attributes without our own tag
        # so we have to count past those.
        body_start_s_index = (
            start_i_index
            + 1
            + len([1 for attr in attrs if not isinstance(attr, TLiteralAttribute)])
        )
        info = (
            last_container_tag,
            attrs,
            start_i_index,
            end_i_index,
            body_start_s_index,
        )
        return Interpolation((interpolate_component, info), "", None, "tdom_component")

    def _stream_raw_text_interpolation(self, last_container_tag, text_t):
        info = (last_container_tag, text_t)
        return Interpolation(
            (interpolate_raw_text, info), "", None, "html_raw_text_template"
        )

    def _stream_escapable_raw_text_interpolation(self, last_container_tag, text_t):
        info = (last_container_tag, text_t)
        return Interpolation(
            (interpolate_escapable_raw_text, info),
            "",
            None,
            "html_escapable_raw_text_template",
        )

    def _stream_text_interpolation(
        self, last_container_tag: str | None, values_index: int
    ):
        info = (last_container_tag, values_index)
        return Interpolation(
            (interpolate_struct_text, info), "", None, "html_normal_interpolation"
        )

    def streamer(
        self, root: TNode, last_container_tag: str | None = None
    ) -> t.Iterable[str | Interpolation]:
        """
        Stream template parts back out so they can be consolidated into a new metadata-aware template.
        """
        q: list[tuple[str | None, TNode | EndTag]] = [(last_container_tag, root)]
        while q:
            last_container_tag, tnode = q.pop()
            match tnode:
                case EndTag(end_tag):
                    yield end_tag
                case TDocumentType(text):
                    yield f"<!doctype {text}>"
                case TComment(ref):
                    text_t = Template(
                        *[
                            part
                            if isinstance(part, str)
                            else Interpolation(part, "", None, "")
                            for part in iter(ref)
                        ]
                    )
                    yield "<!--"
                    yield self._stream_comment_interpolation(text_t)
                    yield "-->"
                case TFragment(children):
                    q.extend(
                        [(last_container_tag, child) for child in reversed(children)]
                    )
                case TComponent(start_i_index, end_i_index, attrs, children):
                    yield self._stream_component_interpolation(
                        last_container_tag, attrs, start_i_index, end_i_index
                    )
                case TElement(tag, attrs, children):
                    yield f"<{tag}"
                    if self.has_dynamic_attrs(attrs):
                        yield self._stream_attrs_interpolation(tag, attrs)
                    else:
                        # @DESIGN: We can't customize the html attrs rendering here because we are not even
                        # in the RENDERER!
                        yield render_html_attrs(
                            coerce_to_html_attrs(
                                resolve_dynamic_attrs(attrs, interpolations=())
                            )
                        )
                    # @DESIGN: This is just a want to have.
                    if self.slash_void and tag in VOID_ELEMENTS:
                        yield " />"
                    else:
                        yield ">"
                    if tag not in VOID_ELEMENTS:
                        q.append((last_container_tag, EndTag(f"</{tag}>")))
                        q.extend([(tag, child) for child in reversed(children)])
                case TText(ref):
                    text_t = Template(
                        *[
                            part
                            if isinstance(part, str)
                            else Interpolation(part, "", None, "")
                            for part in iter(ref)
                        ]
                    )
                    if last_container_tag in CDATA_CONTENT_ELEMENTS:
                        # Must be handled all at once.
                        yield self._stream_raw_text_interpolation(
                            last_container_tag, text_t
                        )
                    elif last_container_tag in RCDATA_CONTENT_ELEMENTS:
                        # We can handle all at once because there are no non-text children and everything must be string-ified.
                        yield self._stream_escapable_raw_text_interpolation(
                            last_container_tag, text_t
                        )
                    else:
                        # Flatten the template back out into the stream because each interpolation can
                        # be escaped as is and structured content can be injected between text anyways.
                        for part in text_t:
                            if isinstance(part, str):
                                yield part
                            else:
                                yield self._stream_text_interpolation(
                                    last_container_tag, part.value
                                )
                case _:
                    raise ValueError(f"Unrecognized tnode: {tnode}")

    def has_dynamic_attrs(self, attrs: t.Sequence[TAttribute]) -> bool:
        for attr in attrs:
            if not isinstance(attr, TLiteralAttribute):
                return True
        return False

    def extract_children_template(
        self, template: Template, body_start_s_index: int, end_i_index: int
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
        assert self.extract_children_template(template, 2, 4) == (
            t'<div>{content} <span>{footer}</span></div>'
        )
        starttag = t'<{comp} attr={attr}>'
        endtag = t'</{comp}>'
        assert template == starttag + self.extract_children_template(template, 2, 4) + endtag
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


@dataclass(frozen=True)
class RenderService:
    transform_api: TransformService

    escape_html_text: Callable = default_escape_html_text

    escape_html_comment: Callable = default_escape_html_comment

    escape_html_content_in_tag: Callable = default_escape_html_content_in_tag

    def get_system(self, **kwargs: object):
        # @DESIGN: Maybe inject more here?
        return {**kwargs}

    def render_template(
        self, template: Template, last_container_tag: str | None = None
    ) -> str:
        """
        Iterate left to right and pause and push new iterators when descending depth-first.

        Every interpolation becomes an iterator.

        Every iterator could return more iterators.

        The last container tag is used to determine how to handle
        text processing.  When working with fragments we might not know the
        container tag until the fragment is included at render-time.
        """
        # @DESIGN: We put all the strings in a list and then ''.join them at
        # the end.
        bf: list[str] = []
        q: list[RenderQueueItem] = []
        q.append(
            (
                last_container_tag,
                self.walk_template(
                    bf, template, self.transform_api.transform_template(template)
                ),
            )
        )
        while q:
            last_container_tag, it = q.pop()
            for interpolator, template, ip_info in it:
                render_queue_item = interpolator(
                    self, bf, last_container_tag, template, ip_info
                )
                if render_queue_item is not None:
                    #
                    # Pause the current iterator and push a new iterator on top of it.
                    #
                    q.append((last_container_tag, it))
                    q.append(render_queue_item)
                    break
        return "".join(bf)

    def resolve_text_without_recursion(
        self, template: Template, container_tag: str, content_t: Template
    ) -> str:
        """
        Resolve the text in the given template without recursing into more structured text.

        This can be bypassed by interpolating an exact match with an object with `__html__()`.

        A non-exact match is not allowed because we cannot process escaping
        across the boundary between other content and the pass-through content.
        """
        if len(content_t.interpolations) == 1 and content_t.strings == ("", ""):
            i_index = t.cast(int, content_t.interpolations[0].value)
            value = template.interpolations[i_index].value
            if value is None or value is False:
                return ""
            elif isinstance(value, str):
                return value
            elif hasattr(value, "__html__"):
                return Markup(value.__html__())
            elif isinstance(value, (Template, Iterable)):
                raise ValueError(
                    f"Recursive includes are not supported within {container_tag}"
                )
            else:
                return str(value)
        else:
            text = []
            for part in content_t:
                if isinstance(part, str):
                    if part:
                        text.append(part)
                    continue
                value = template.interpolations[part.value].value
                if value is None or value is False:
                    continue
                elif isinstance(value, str):
                    if value:
                        text.append(value)
                elif isinstance(value, (Template, Iterable)):
                    raise ValueError(
                        f"Recursive includes are not supported within {container_tag}"
                    )
                elif hasattr(value, "__html__"):
                    raise ValueError(
                        f"Non-exact trusted interpolations are not supported within {container_tag}"
                    )
                else:
                    value_str = str(value)
                    if value_str:
                        text.append(value_str)
            return "".join(text)

    def resolve_attrs(
        self, attrs: t.Sequence[TAttribute], template: Template
    ) -> AttributesDict:
        return resolve_dynamic_attrs(attrs, template.interpolations)

    def walk_template_with_context(
        self,
        bf: list[str],
        template: Template,
        struct_t: Template,
        context_values: tuple[tuple[ContextVar, object]] | None = None,
    ) -> Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]]:
        if context_values:
            cm = ContextVarSetter(context_values=context_values)
        else:
            cm = nullcontext()
        with cm:
            yield from self.walk_template(bf, template, struct_t)

    def walk_template(
        self, bf: list[str], template: Template, struct_t: Template
    ) -> Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]]:
        strings = struct_t.strings
        ips = struct_t.interpolations
        last_str = len(strings) - 1
        idx = 0
        while idx != last_str:
            if strings[idx]:
                bf.append(strings[idx])
            # @TODO: Should the template just be jammed in here too?
            populate, value = ips[idx].value
            yield (populate, template, value)
            idx += 1
        if strings[idx]:
            bf.append(strings[idx])


class ContextVarSetter:
    """
    Context manager for working with many context vars (instead of only 1).

    This is meant to be created, used immediately and then discarded.

    This allows for dynamically specifying a tuple of var / value pairs that
    another part of the program can use to wrap some called code without knowing
    anything about either.
    """

    context_values: tuple[tuple[ContextVar, object], ...]  # Cvar / value pair.
    tokens: tuple[Token, ...]

    def __init__(self, context_values=()):
        self.context_values = context_values
        self.tokens = ()

    def __enter__(self):
        """Set every given context var to its paired value."""
        self.tokens = tuple([var.set(val) for var, val in self.context_values])

    def __exit__(self, exc_type, exc_value, traceback):
        """Reset every given context var."""
        for idx, var_value in enumerate(self.context_values):
            var_value[0].reset(self.tokens[idx])


def render_service_factory():
    return RenderService(transform_api=TransformService())


def cached_render_service_factory():
    return RenderService(transform_api=CachedTransformService())


#
# SHIM: This is here until we can find a way to make a configurable cache.
#
@dataclass(frozen=True)
class CachedTransformService(TransformService):
    @functools.lru_cache(512)
    def _transform_template(self, cached_template: CachableTemplate) -> Template:
        return super().transform_template(cached_template.template)

    def transform_template(self, template: Template) -> Template:
        ct = CachableTemplate(template)
        return self._transform_template(ct)
