from dataclasses import dataclass
from string.templatelib import Interpolation, Template
from typing import Callable
from collections.abc import Iterable, Sequence
import typing as t
from contextlib import nullcontext
from contextvars import ContextVar, Token
import functools
import inspect

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
    escape_html_script as default_escape_html_script,
    escape_html_style as default_escape_html_style,
    escape_html_text as default_escape_html_text,
    escape_html_comment as default_escape_html_comment,
)
from .utils import CachableTemplate
from .processor import (
    _resolve_t_attrs as resolve_dynamic_attrs,
    _resolve_html_attrs as coerce_to_html_attrs,
    AttributesDict,
    _prep_component_kwargs,
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
        Populates an interpolation or returns iterator to descend into.

        render_api
            The current render api, provides various helper methods.
        bf
            A list-like output buffer.
        last_container_tag
            The last HTML tag known for this interpolation or None if unknown.
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
            resolve_text_without_recursion(template, container_tag, comment_t),
            allow_markup=True,
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


type ComponentReturnValueSimple = None | Template
type ComponentReturnConfig = dict[str, object]
type ComponentReturnValue = (
    ComponentReturnValueSimple
    | tuple[ComponentReturnValueSimple, ComponentReturnConfig]
)


type ComponentClassSig = Callable[..., Callable[[], ComponentReturnValue]]


def invoke_component_class(
    component_callable: ComponentClassSig,
    kwargs: dict[str, object],
) -> tuple[ComponentReturnValueSimple, tuple[tuple[ContextVar, object], ...]]:
    return process_component_return_value(component_callable(**kwargs)())


type ComponentFunctionSig = Callable[..., ComponentReturnValue]


def invoke_component_function(
    component_callable: ComponentFunctionSig,
    kwargs: dict[str, object],
) -> tuple[ComponentReturnValueSimple, tuple[tuple[ContextVar, object], ...]]:
    return process_component_return_value(component_callable(**kwargs))


def process_component_return_value(
    res: ComponentReturnValue,
) -> tuple[ComponentReturnValueSimple, tuple[tuple[ContextVar, object], ...]]:
    # @DESIGN: Determine return signature via runtime inspection?
    if isinstance(res, tuple):
        if len(res) != 2:
            raise ValueError(
                f"Tuple form of component return value must be len() 2, not: {len(res)}"
            )
        else:
            result_template, comp_info = res
            # @DESIGN: Use open-ended dict for opt-in second return argument?
            context_values = comp_info.get("context_values", ())
            if not isinstance(context_values, tuple):
                raise TypeError(
                    f"Context values must be a tuple, found {type(context_values)}."
                )
            # @TYPING: We need runtime checks for typing but uv does not
            # pick them up so we put each item back into a list and then back into a
            # tuple and for some reason that works...
            cvs = []
            for entry in context_values:
                if not isinstance(entry, tuple):
                    raise ValueError(
                        f"Entries for context_values must be 2-tuples but found type: {type(entry)}."
                    )
                elif len(entry) != 2:
                    raise ValueError(
                        f"Entries for context_values must be 2-tuples but found len(): {len(entry)}."
                    )
                elif not isinstance(entry[0], ContextVar):
                    raise ValueError(
                        f"Invalid context variable in component return value: {type(entry[0])}"
                    )
                else:
                    # @TYPING: See below
                    cvs.append(entry)
            # @TYPING: Hack to make uv pickup runtime type checks, pyright seems to work ok without.
            context_values = tuple(cvs)
    else:
        result_template = res
        context_values = ()

    return result_template, context_values


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
    start_i = template.interpolations[start_i_index]
    component_callable = start_i.value
    if start_i_index != end_i_index and end_i_index is not None:
        # @DESIGN: We extract the children template from the original outer template.
        children_template = extract_embedded_template(
            template, body_start_s_index, end_i_index
        )
        if component_callable != template.interpolations[end_i_index].value:
            raise TypeError(
                "Component callable in start tag must match component callable in end tag."
            )
    else:
        children_template = Template("")

    # @DESIGN: Inject system vars via manager?
    system_kwargs = render_api.get_system(
        children=children_template  # @DESIGN: children_struct=children_struct_t ?
    )

    if not callable(component_callable):
        raise TypeError("Component callable must be callable.")

    kwargs = _prep_component_kwargs(
        get_callable_info(component_callable),
        resolve_dynamic_attrs(attrs, template.interpolations),
        system_kwargs=system_kwargs,
    )

    if inspect.isclass(component_callable):
        component_callable = t.cast(ComponentClassSig, component_callable)
        result_template, context_values = invoke_component_class(
            component_callable, kwargs
        )
    else:
        component_callable = t.cast(ComponentFunctionSig, component_callable)
        result_template, context_values = invoke_component_function(
            component_callable, kwargs
        )

    if isinstance(result_template, Template):
        if result_template.strings == ("",):
            # DO NOTHING
            return
        result_struct = render_api.transform_api.transform_template(result_template)
        if context_values:
            walker = render_api.walk_template_with_context(
                bf, result_template, result_struct, context_values=context_values
            )
        else:
            walker = render_api.walk_template(bf, result_template, result_struct)
        return (container_tag, iter(walker))
    elif result_template is None:
        # DO NOTHING
        return
    else:
        raise ValueError(f"Unknown component return value: {type(result_template)}")


type InterpolateRawTextsFromTemplateInfo = tuple[str, Template]


def interpolate_raw_texts_from_template(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    """
    Interpolate and join a template of raw texts together and escape them.

    @NOTE: This interpolator expects a Template.
    """
    container_tag, content_t = t.cast(InterpolateRawTextsFromTemplateInfo, ip_info)
    content = resolve_text_without_recursion(template, container_tag, content_t)
    if container_tag == "script":
        bf.append(
            render_api.escape_html_script(
                container_tag,
                content,
                allow_markup=True,
            )
        )
    elif container_tag == "style":
        bf.append(
            render_api.escape_html_style(
                container_tag,
                content,
                allow_markup=True,
            )
        )
    else:
        raise NotImplementedError(f"Container tag {container_tag} is not supported.")


type InterpolateEscapableRawTextsFromTemplateInfo = tuple[str, Template]


def interpolate_escapable_raw_texts_from_template(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    """
    Interpolate and join a template of escapable raw texts together and escape them.

    @NOTE: This interpolator expects a Template.
    """
    container_tag, content_t = t.cast(
        InterpolateEscapableRawTextsFromTemplateInfo, ip_info
    )
    assert container_tag == "title" or container_tag == "textarea"
    bf.append(
        render_api.escape_html_text(
            resolve_text_without_recursion(template, container_tag, content_t),
        )
    )


type InterpolateNormalTextInfo = tuple[str, int]


def interpolate_normal_text_from_interpolation(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    """
    Interpolate a single normal text either into structured content or an escaped string.

    @NOTE: This expects a SINGLE interpolation referenced via i_index.
    """
    container_tag, ip_index = t.cast(InterpolateNormalTextInfo, ip_info)
    value = format_interpolation(template.interpolations[ip_index])
    return interpolate_normal_text_from_value(
        render_api, bf, last_container_tag, template, (container_tag, value)
    )


type InterpolateNormalTextValueInfo = tuple[str | None, object]


def interpolate_normal_text_from_value(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    """
    Resolve a single text value interpolated within a normal element.

    @NOTE: This could be a str(), None, Iterable, Template or HasHTMLDunder.
    """
    container_tag, value = t.cast(InterpolateNormalTextValueInfo, ip_info)
    if container_tag is None:
        container_tag = last_container_tag

    if isinstance(value, str):
        # @DESIGN: Objects with `__html__` must be wrapped with markupsafe.Markup.
        bf.append(render_api.escape_html_text(value))
    elif isinstance(value, Template):
        return (
            container_tag,
            iter(
                render_api.walk_template(
                    bf, value, render_api.transform_api.transform_template(value)
                )
            ),
        )
    elif isinstance(value, Iterable):
        return (
            container_tag,
            (
                (
                    interpolate_normal_text_from_value,
                    template,
                    (container_tag, v if v is not None else None),
                )
                for v in t.cast(Iterable, value)
            ),
        )
    elif value is None:
        # @DESIGN: Ignore None.
        return
    else:
        # @DESIGN: Everything that isn't an object we recognize is
        # coerced to a str() and emitted.
        bf.append(render_api.escape_html_text(str(value)))


type InterpolateDynamicTextsFromTemplateInfo = tuple[None, Template]


def interpolate_dynamic_texts_from_template(
    render_api: RenderService,
    bf: list[str],
    last_container_tag: str | None,
    template: Template,
    ip_info: InterpolateInfo,
) -> RenderQueueItem | None:
    container_tag, text_t = t.cast(InterpolateDynamicTextsFromTemplateInfo, ip_info)
    # Try to use the dynamic container if possible.
    if container_tag is None:
        container_tag = last_container_tag
    if container_tag is None:
        raise NotImplementedError(
            "We cannot interpolate texts without knowing what tag they are contained in."
        )
    elif container_tag in CDATA_CONTENT_ELEMENTS:
        return interpolate_raw_texts_from_template(
            render_api, bf, last_container_tag, template, (container_tag, text_t)
        )
    elif container_tag in RCDATA_CONTENT_ELEMENTS:
        return interpolate_escapable_raw_texts_from_template(
            render_api, bf, last_container_tag, template, (container_tag, text_t)
        )
    else:
        return (
            container_tag,
            iter(walk_dynamic_template(bf, template, text_t, container_tag)),
        )


def walk_dynamic_template(
    bf: list[str], template: Template, text_t: Template, container_tag: str
) -> t.Iterable[tuple[InterpolatorProto, Template, InterpolateInfo]]:
    """
    Walk a `Text()` template that we determined was usable at runtime.

    This happens when a container tag isn't resolvable at parse time and we
    have to discover it at runtime.

    bf:
      The buffer to write strings out to.
    template:
      The original values template.
    text_t:
      A template with i_index references to the original values template.
    container_tag:
      The tag of the containing element.
    """
    for part in text_t:
        if isinstance(part, str):
            bf.append(part)
        else:
            ip_info = (container_tag, part.value)
            yield (interpolate_normal_text_from_interpolation, template, ip_info)


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

    uppercase_doctype: bool = False  # DOCTYPE vs doctype

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

    def _stream_raw_texts_interpolation(
        self, last_container_tag: str, text_t: Template
    ):
        info = (last_container_tag, text_t)
        return Interpolation(
            (interpolate_raw_texts_from_template, info), "", None, "html_raw_texts"
        )

    def _stream_escapable_raw_texts_interpolation(
        self, last_container_tag: str, text_t: Template
    ):
        info = (last_container_tag, text_t)
        return Interpolation(
            (interpolate_escapable_raw_texts_from_template, info),
            "",
            None,
            "html_escapable_raw_texts",
        )

    def _stream_normal_text_interpolation(
        self, last_container_tag: str, values_index: int
    ):
        info = (last_container_tag, values_index)
        return Interpolation(
            (interpolate_normal_text_from_interpolation, info),
            "",
            None,
            "html_normal_text",
        )

    def _stream_dynamic_texts_interpolation(
        self, last_container_tag: None, text_t: Template
    ):
        info = (last_container_tag, text_t)
        return Interpolation(
            (interpolate_dynamic_texts_from_template, info),
            "",
            None,
            "html_dynamic_text",
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
                    if self.uppercase_doctype:
                        yield f"<!DOCTYPE {text}>"
                    else:
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
                    if ref.is_literal:
                        yield ref.strings[0]  # Trust literals.
                    elif last_container_tag is None:
                        # We can't know how to handle this right now, so wait until render time and if
                        # we still cannot know then probably fail.
                        yield self._stream_dynamic_texts_interpolation(
                            last_container_tag, text_t
                        )
                    elif last_container_tag in CDATA_CONTENT_ELEMENTS:
                        # Must be handled all at once.
                        yield self._stream_raw_texts_interpolation(
                            last_container_tag, text_t
                        )
                    elif last_container_tag in RCDATA_CONTENT_ELEMENTS:
                        # We can handle all at once because there are no non-text children and everything must be string-ified.
                        yield self._stream_escapable_raw_texts_interpolation(
                            last_container_tag, text_t
                        )
                    else:
                        # Flatten the template back out into the stream because each interpolation can
                        # be escaped as is and structured content can be injected between text anyways.
                        for part in text_t:
                            if isinstance(part, str):
                                yield part
                            else:
                                yield self._stream_normal_text_interpolation(
                                    last_container_tag, part.value
                                )
                case _:
                    raise ValueError(f"Unrecognized tnode: {tnode}")

    def has_dynamic_attrs(self, attrs: t.Sequence[TAttribute]) -> bool:
        """
        Determine if any attributes with interpolations are in attrs sequence.

        This is mainly used to tell if we can pre-emptively serialize an
        element's attributes (or not).
        """
        for attr in attrs:
            if not isinstance(attr, TLiteralAttribute):
                return True
        return False


def resolve_text_without_recursion(
    template: Template, container_tag: str, content_t: Template
) -> str | None:
    """
    Resolve the text in the given template without recursing into more structured text.

    This can be bypassed by interpolating an exact match with an object with `__html__()`.

    A non-exact match is not allowed because we cannot process escaping
    across the boundary between other content and the pass-through content.
    """
    # @TODO: We should use formatting but not in a way that
    # auto-interpolates structured values.

    if len(content_t.interpolations) == 1 and content_t.strings == ("", ""):
        i_index = t.cast(int, content_t.interpolations[0].value)
        value = template.interpolations[i_index].value
        if value is None:
            return None
        elif isinstance(value, str):
            # @DESIGN: Markup() must be used explicitly if you want __html__ supported.
            return value
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
            if value is None:
                continue
            elif (
                type(value) is str
            ):  # type() check to avoid subclasses, probably something smarter here
                if value:
                    text.append(value)
            elif not isinstance(value, str) and isinstance(value, (Template, Iterable)):
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
        if text:
            return "".join(text)
        else:
            return None


def determine_body_start_s_index(tcomp):
    """
    Calculate the strings index when the embedded template starts after a component start tag.

    This doesn't actually know or care if the component has a body it just
    counts past the dynamic (non-literal) attributes and returns the first strings index
    offset by interpolation index for the component callable itself.
    """
    return (
        tcomp.start_i_index
        + 1
        + len([1 for attr in tcomp.attrs if not isinstance(attr, TLiteralAttribute)])
    )


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


@dataclass(frozen=True)
class RenderService:
    transform_api: TransformService

    escape_html_text: Callable = default_escape_html_text

    escape_html_comment: Callable = default_escape_html_comment

    escape_html_script: Callable = default_escape_html_script

    escape_html_style: Callable = default_escape_html_style

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

    def resolve_attrs(
        self, attrs: t.Sequence[TAttribute], template: Template
    ) -> AttributesDict:
        return resolve_dynamic_attrs(attrs, template.interpolations)

    def walk_template_with_context(
        self,
        bf: list[str],
        template: Template,
        struct_t: Template,
        context_values: tuple[tuple[ContextVar, object], ...] = (),
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


def render_service_factory(transform_api_kwargs=None):
    return RenderService(transform_api=TransformService(**(transform_api_kwargs or {})))


def cached_render_service_factory(transform_api_kwargs=None):
    return RenderService(
        transform_api=CachedTransformService(**(transform_api_kwargs or {}))
    )


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
