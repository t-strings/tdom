from dataclasses import dataclass
from string.templatelib import Interpolation, Template
from typing import Callable
from collections.abc import Iterable, Sequence
import typing as t
from contextlib import nullcontext
from contextvars import ContextVar, Token
import functools
from markupsafe import Markup

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
from .processor import _resolve_t_attrs, AttributesDict, _resolve_html_attrs


@dataclass
class EndTag:
    end_tag: str


def render_html_attrs(html_attrs: HTMLAttributesDict, escape: Callable = default_escape_html_text) -> str:
    return ''.join((f' {k}="{v}"' if v is not None else f' {k}' for k, v in html_attrs.items()))


class Interpolator(t.Protocol):

    def __call__(self, render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
        """
        Populates an interpolation or returns iterator to decende into.

        If recursion is required then pushes current iterator
        render_api
            The current render api, provides various helper methods to the interpolator.
        q
            A list-like queue of iterators paired with the container tag the results are in.
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
        pass


type InterpolationInfo = object | None


type RenderQueueItem = tuple[str | None, Iterable[tuple[Interpolator, Template, InterpolationInfo]]]


def interpolate_comment(render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
    container_tag, comment_t = ip_info
    assert container_tag == '<!--'
    bf.append(render_api.escape_html_comment(render_api.resolve_text_without_recursion(template, container_tag, comment_t)))


def interpolate_attrs(render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
    container_tag, attrs = ip_info
    html_attrs = render_api.interpolate_attrs(attrs, template)
    attrs_str = render_html_attrs(_resolve_html_attrs(html_attrs))
    bf.append(attrs_str)


def interpolate_component(render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
    """
    - Extract embedded template or use empty template.
    - Transform embedded template into struct template.
    - Resolve attrs but don't stringify.
    - Resolve callable.
    - Invoke callable with attrs, embedded template, embedded struct template. (no garbage barge? how can we pass the cache?)
    - If callable returns a result template then
         * transform it to a struct template
         * iteratively recurse into that result template and start outputting it
    """
    (container_tag, attrs, start_i_index, end_i_index, body_start_s_index) = ip_info
    if start_i_index != end_i_index and end_i_index is not None:
        embedded_template = render_api.transform_api.extract_embedded_template(template, body_start_s_index, end_i_index)
    else:
        embedded_template = Template('')
    embedded_struct_t = render_api.process_template(embedded_template)
    attrs = render_api.interpolate_attrs(attrs, template)
    component_callable = template.interpolations[start_i_index].value
    if start_i_index != end_i_index and end_i_index is not None and component_callable != template.interpolations[end_i_index].value:
        raise TypeError('Component callable in start tag must match component callable in end tag.')
    result_template, context_values = component_callable(attrs, embedded_template, embedded_struct_t)
    if result_template:
        result_struct = render_api.process_template(result_template)
        if context_values:
            walker = render_api.walk_template_with_context(bf, result_template, result_struct, context_values=context_values)
        else:
            walker = render_api.walk_template(bf, result_template, result_struct)
        return (container_tag, iter(walker))


def interpolate_raw_text(render_api, q, bf, last_container_tag, template, value) -> RenderQueueItem | None:
    container_tag, content_t = value
    bf.append(render_api.escape_html_content_in_tag(container_tag, render_api.resolve_text_without_recursion(template, container_tag, content_t)))


def interpolate_escapable_raw_text(render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
    container_tag, content_t = ip_info
    bf.append(render_api.escape_html_text(render_api.resolve_text_without_recursion(template, container_tag, content_t)))


def interpolate_struct_text(render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
    container_tag, ip_index = ip_info
    # @TODO: We just completely ignore any conversion or format_spec here.
    # This is actually a much larger problem/decision of how can a user give us more information about what to do
    # with their input AND should that be a one-off OR cached with the structured template forever.
    # For example
    #   - The 3rd interpolation will always be a html-aware Template string
    #   - The 4th interpolation will be an iterator of html-aware Template strings
    #   - The 5th interpolation will be an iterator of strings to render and escape.
    value = template.interpolations[ip_index].value # data provided to a parsed t-string
    return interpolate_text(render_api, q, bf, last_container_tag, template, (container_tag, value))


def interpolate_user_text(render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
    return interpolate_text(render_api, q, bf, last_container_tag, template, ip_info)


def interpolate_text(render_api, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem | None:
    container_tag, value = ip_info
    if container_tag is None:
        container_tag = last_container_tag

    #
    # Try to optimize past this block if the value is a str.
    #
    if not isinstance(value, str):
        if isinstance(value, Template):
            return (container_tag, iter(render_api.walk_template(bf, value, render_api.process_template(value))))
        elif isinstance(value, Sequence) or hasattr(value, '__iter__'):
            return (container_tag, (((interpolate_user_text, template, (None, v)) for v in iter(value))))
        elif value is False or value is None:
            # Do nothing here, we don't even need to yield ''.
            return

    if container_tag not in ('style', 'script', 'title', 'textarea', '<!--'):
        if hasattr(value, '__html__'):
            bf.append(value.__html__())
        else:
            bf.append(render_api.escape_html_text(value))
    else:
        # @TODO: How could this happen?
        raise ValueError(f'We cannot escape text within {container_tag} when multiple interpolations could occur.')
        #bf.append(render_api.escape_html_content_in_tag(container_tag, str(value)))


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

    slash_void: bool = False # Apply a xhtml-style slash to void html elements.

    def transform_template(self, values_template: Template) -> Template:
        """ Transform the given template into a template for rendering. """
        struct_node = self.to_struct_node(values_template)
        return self.to_struct_template(struct_node)

    def to_struct_node(self, values_template: Template) -> TNode:
        return TemplateParser.parse(values_template)

    def to_struct_template(self, struct_node: TNode) -> Template:
        """ Recombine stream of tokens from node trees into a new template. """
        return Template(*self.streamer(struct_node))

    def _stream_comment_interpolation(self, text_t):
        info = ('<!--', text_t)
        return Interpolation((interpolate_comment, info), '', None, 'html_comment_template')

    def _stream_attrs_interpolation(self, last_container_tag, attrs):
        info = (last_container_tag, attrs)
        return Interpolation((interpolate_attrs, info), '', None, 'html_attrs_seq')

    def _stream_component_interpolation(self, last_container_tag, attrs, start_i_index, end_i_index):
        # If the interpolation is at 1, then the opening string starts inside at least string 2 (+1)
        # but it can't start until after any dynamic attributes without our own tag
        # so we have to count past those.
        body_start_s_index  = start_i_index + 1 + len([1 for attr in attrs if not isinstance(attr, TLiteralAttribute)])
        info = (last_container_tag, attrs, start_i_index, end_i_index, body_start_s_index)
        return Interpolation((interpolate_component, info), '', None, 'tdom_component')

    def _stream_raw_text_interpolation(self, last_container_tag, text_t):
        info = (last_container_tag, text_t)
        return Interpolation((interpolate_raw_text, info), '', None, 'html_raw_text_template')

    def _stream_escapable_raw_text_interpolation(self, last_container_tag, text_t):
        info = (last_container_tag, text_t)
        return Interpolation((interpolate_escapable_raw_text, info), '', None, 'html_escapable_raw_text_template')

    def _stream_text_interpolation(self, last_container_tag: str|None, values_index: int):
        info = (last_container_tag, values_index)
        return Interpolation((interpolate_struct_text, info), '', None, 'html_normal_interpolation')

    def streamer(self, root: TNode, last_container_tag: str|None=None) -> t.Iterable[str|Interpolation]:
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
                    yield f'<!doctype {text}>'
                case TComment(ref):
                    text_t = Template(*[part if isinstance(part, str) else Interpolation(part, '', None, '') for part in iter(ref)])
                    yield '<!--'
                    yield self._stream_comment_interpolation(text_t)
                    yield '-->'
                case TFragment(children):
                    q.extend([(last_container_tag, child) for child in reversed(children)])
                case TComponent(start_i_index, end_i_index, attrs, children):
                    yield self._stream_component_interpolation(last_container_tag, attrs, start_i_index, end_i_index)
                case TElement(tag, attrs, children):
                    yield f'<{tag}'
                    if self.has_dynamic_attrs(attrs):
                        yield self._stream_attrs_interpolation(tag, attrs)
                    else:
                        yield render_html_attrs(_resolve_html_attrs(_resolve_t_attrs(attrs, interpolations=())))
                    # This is just a want to have.
                    if self.slash_void and tag in VOID_ELEMENTS:
                        yield ' />'
                    else:
                        yield '>'
                    if tag not in VOID_ELEMENTS:
                        q.append((last_container_tag, EndTag(f'</{tag}>')))
                        q.extend([(tag, child) for child in reversed(children)])
                case TText(ref):
                    text_t = Template(*[part if isinstance(part, str) else Interpolation(part, '', None, '') for part in iter(ref)])
                    if last_container_tag in CDATA_CONTENT_ELEMENTS:
                        # Must be handled all at once.
                        yield self._stream_raw_text_interpolation(last_container_tag, text_t)
                    elif last_container_tag in RCDATA_CONTENT_ELEMENTS:
                        # We can handle all at once because there are no non-text children and everything must be string-ified.
                        yield self._stream_escapable_raw_text_interpolation(last_container_tag, text_t)
                    else:
                        # Flatten the template back out into the stream because each interpolation can
                        # be escaped as is and structured content can be injected between text anyways.
                        for part in text_t:
                            if isinstance(part, str):
                                yield part
                            else:
                                yield self._stream_text_interpolation(last_container_tag, part.value)
                case _:
                    raise ValueError(f'Unrecognized tnode: {tnode}')

    def has_dynamic_attrs(self, attrs: t.Sequence[TAttribute]) -> bool:
        for attr in attrs:
            if not isinstance(attr, TLiteralAttribute):
                return True
        return False

    def extract_embedded_template(self, template: Template, body_start_s_index: int, end_i_index: int):
        """
        Extract the template parts exclusively from start tag to end tag.

        @TODO: "There must be a better way."
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
        parts[0] = parts[0][parts[0].find('>')+1:]
        # Now trim the last part (could also be the first) to the start of the closing tag.
        parts[-1] = parts[-1][:parts[-1].rfind('<')]
        return Template(*parts)


@dataclass(frozen=True)
class RenderService:

    transform_api: TransformService

    escape_html_text: Callable = default_escape_html_text

    escape_html_comment: Callable = default_escape_html_comment

    escape_html_content_in_tag: Callable = default_escape_html_content_in_tag

    def render_template(self, template, last_container_tag=None) -> str:
        """
        Iterate left to right and pause and push new iterators when descending depth-first.

        Every interpolation becomes an iterator.

        Every iterator could return more iterators.

        The last container tag is used to determine how to handle
        text processing.  When working with fragments we might not know the
        container tag until the fragment is included at render-time.
        """
        bf: list[str] = []
        q: list[RenderQueueItem] = []
        q.append((last_container_tag, self.walk_template(bf, template, self.process_template(template))))
        while q:
            last_container_tag, it = q.pop()
            for (interpolator, template, ip_info) in it:
                render_queue_item = interpolator(self, q, bf, last_container_tag, template, ip_info)
                if render_queue_item is not None:
                    #
                    # Pause the current iterator and push a new iterator on top of it.
                    #
                    q.append((last_container_tag, it))
                    q.append(render_queue_item)
                    break
        return ''.join(bf)

    def resolve_text_without_recursion(self, template, container_tag, content_t) -> str:
        parts = list(content_t)
        exact = len(parts) == 1 and len(content_t.interpolations) == 1
        if exact:
            value = template.interpolations[parts[0].value].value
            if value is None or value is False:
                return ''
            elif isinstance(value, str):
                return value
            elif hasattr(value, '__html__'):
                return Markup(value.__html__())
            elif isinstance(value, (Template, Iterable)):
                raise ValueError(f'Recursive includes are not supported within {container_tag}')
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
                elif isinstance(value , str):
                    if value:
                        text.append(value)
                    elif isinstance(value, (Template, Iterable)):
                        raise ValueError(f'Recursive includes are not supported within {container_tag}')
                    elif hasattr(value, '__html__'):
                        raise ValueError(f'Non-exact trusted interpolations are not supported within {container_tag}')
                    else:
                        value_str = str(value)
                        if value_str:
                            text.append(value_str)
            return ''.join(text)

    def process_template(self, template):
        """ This is just a wrap-point for caching. """
        return self.transform_api.transform_template(template)

    def interpolate_attrs(self, attrs, template) -> AttributesDict:
        """ Plug `template` values into any attribute interpolations. """
        return _resolve_t_attrs(attrs, template.interpolations)

    def walk_template_with_context(self, bf, template, struct_t, context_values=None):
        if context_values:
            cm = ContextVarSetter(context_values=context_values)
        else:
            cm = nullcontext()
        with cm:
            yield from self.walk_template(bf, template, struct_t)

    def walk_template(self, bf, template, struct_t):
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
    context_values: tuple[tuple[ContextVar, object],...]
    tokens: tuple[Token,...]

    def __init__(self, context_values=()):
        self.context_values = context_values
        self.tokens = ()

    def __enter__(self):
        self.tokens = tuple([var.set(val) for var, val in self.context_values])

    def __exit__(self, exc_type, exc_value, traceback):
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
    def _transform_template(self, cached_template: CachableTemplate) -> TNode:
        return super().transform_template(cached_template.template)

    def transform_template(self, template: Template) -> TNode:
        ct = CachableTemplate(template)
        return self._transform_template(ct)
