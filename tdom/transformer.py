from dataclasses import dataclass, field
from string.templatelib import Interpolation, Template
from io import StringIO, BufferedWriter
from typing import Callable
from collections.abc import Iterable
import typing as t
from collections import deque

from .parser import parse_html
from .nodes import (
    TNode,
    TFragment,
    TElement,
    TText,
    DocumentType,
    TComment,
    ComponentInfo,
    VOID_ELEMENTS,
    CDATA_CONTENT_ELEMENTS,
    RCDATA_CONTENT_ELEMENTS,
    )
from .escaping import (
    escape_html_content_in_tag as default_escape_html_content_in_tag,
    escape_html_text as default_escape_html_text,
    escape_html_script as default_escape_html_script,
    escape_html_comment as default_escape_html_comment,
    )
from .processor import LastUpdatedOrderedDict


@t.runtime_checkable
class HasHTMLDunder(t.Protocol):
    def __html__(self) -> str: ...  # pragma: no cover


@dataclass
class EndTag:
    end_tag: str


BREAK_ITR = 'break_itr'


class Interpolator(t.Protocol):

    def __call__(self, render_api, struct_cache, q, bf, last_container_tag, template, value) -> RenderQueueItem:
        """
        Populates an interpolation or returns iterator to decende into.

        If recursion is required then pushes current iterator
        render_api
        struct_cache
        q
            A list-like queue of iterators paired with the container tag the results are in.
        bf
            A list-like output buffer.
        last_container_tag
            The last HTML tag known for this interpolation, this cannot always be 100% accurate.
        template
            The "values" template that is being used to fulfill interpolations.
        value
            The value of the "structure" template interpolation or a standalone value usually
            from a user supplied iterator.

        """
        pass

type InterpolationInfo = object | None
type RenderQueueItem = tuple[str | None, Iteratable[tuple[Interpolator, Template, InterpolationInfo]]]


def interpolate_comment(render_api, struct_cache, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem:
    container_tag, comment_t = ip_info
    assert container_tag == '<!--'
    bf.append(render_api.escape_html_comment(render_api.resolve_text_without_recursion(template, container_tag, comment_t)))


def interpolate_attrs(render_api, struct_cache, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem:
    container_tag, attrs = ip_info
    attrs = render_api.resolve_attrs(render_api.interpolate_attrs(attrs, template))
    attrs_str = ''.join(f' {k}' if v is True else f' {k}="{render_api.escape_html_text(v)}"' for k, v in attrs.items() if v is not None and v is not False)
    bf.append(attrs_str)


def interpolate_component(render_api, struct_cache, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem:
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
    (container_tag, attrs, start_template_interpolation_index, start_template_string_index, end_template_string_index) = ip_info
    if end_template_string_index is not None:
        embedded_template = render_api.transform_api.extract_embedded_template(template, start_template_string_index, end_template_string_index)
    else:
        embedded_template = Template('')
    embedded_struct_t = render_api.process_template(embedded_template, struct_cache)
    attrs = render_api.resolve_attrs(render_api.interpolate_attrs(attrs, template))
    component_callable = template.interpolations[start_template_interpolation_index].value
    result_template = component_callable(attrs, embedded_template, embedded_struct_t)
    if result_template:
        return (container_tag, iter(render_api.walk_template(bf, result_template, render_api.process_template(result_template, struct_cache))))


def interpolate_raw_text(render_api, struct_cache, q, bf, last_container_tag, template, value) -> RenderQueueItem:
    container_tag, content_t = value
    bf.append(render_api.escape_html_content_in_tag(container_tag, render_api.resolve_text_without_recursion(template, container_tag, content_t)))


def interpolate_escapable_raw_text(render_api, struct_cache, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem:
    container_tag, content_t = ip_info
    bf.append(render_api.escape_html_text(render_api.resolve_text_without_recursion(template, container_tag, content_t)))


def interpolate_struct_text(render_api, struct_cache, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem:
    container_tag, ip_index = ip_info
    value = template.interpolations[ip_index].value # data provided to a parsed t-string
    return interpolate_text(render_api, struct_cache, q, bf, last_container_tag, template, (container_tag, value))


def interpolate_user_text(render_api, struct_cache, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem:
    return interpolate_text(render_api, struct_cache, q, bf, last_container_tag, template, ip_info)


def interpolate_text(render_api, struct_cache, q, bf, last_container_tag, template, ip_info) -> RenderQueueItem:
    container_tag, value = ip_info
    if container_tag is None:
        container_tag = last_container_tag

    if isinstance(value, Template):
        return (container_tag, iter(render_api.walk_template(bf, value, render_api.process_template(value, struct_cache))))
    elif hasattr(value, '__iter__'):
        return (container_tag, (((interpolate_user_text, template, (None, v)) for v in iter(value))))
    elif value is False or value is None:
        # Do nothing here, we don't even need to yield ''.
        return
    else:
        if container_tag not in ('style', 'script', 'title', 'textarea', '<!--'):
            if hasattr(value, '__html__'):
                bf.append(value.__html__())
            else:
                bf.append(render_api.escape_html_text(value))
        else:
            bf.append(render_api.escape_html_content_in_tag(container_tag, str(value)))


@dataclass
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

    def to_struct_node(self, values_template: Template) -> Node:
        return parse_html(values_template)

    def to_struct_template(self, struct_node: Node) -> Template:
        """ Recombine stream of tokens from node trees into a new template. """
        return Template(*self.streamer(struct_node))

    def _stream_comment_interpolation(self, text_t):
        info = ('<!--', text_t, comment_interpolator)
        return Interpolation((interpolate_comment, info), '', None, 'html_comment_template')

    def _stream_attrs_interpolation(self, last_container_tag, attrs):
        info = (last_container_tag, attrs)
        return Interpolation((interpolate_attrs, info), '', None, 'html_attrs_seq')

    def _stream_component_interpolation(self, last_container_tag, attrs, comp_info):
        info = (last_container_tag, attrs, comp_info.starttag_interpolation_index, comp_info.strings_slice_begin, comp_info.strings_slice_end)
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

    def streamer(self, root: TNode, last_container_tag: str|None=None) -> Generator[str|Interpolation, ...]:
        """
        Stream template parts back out so they can be consolidated into a new metadata-aware template.
        """
        q = [(last_container_tag, root)]
        while q:
            last_container_tag, tnode = q.pop()
            match tnode:
                case EndTag(end_tag):
                    yield end_tag
                case DocumentType(text):
                    yield f'<!doctype {text}>'
                case TComment(text_t):
                    yield '<!--'
                    yield self._stream_comment_interpolation(text_t)
                    yield '-->'
                case TFragment(children):
                    q.extend([(last_container_tag, child) for child in reversed(children)])
                case TElement(tag, attrs, children, component_info):
                    if component_info is None:
                        yield f'<{tag}'
                        if self.has_dynamic_attrs(attrs):
                            yield self._stream_attrs_interpolation(tag, attrs)
                        else:
                            yield self.static_attrs_to_str(attrs)
                        # This is just a want to have.
                        if self.slash_void and tag in VOID_ELEMENTS:
                            yield ' />'
                        else:
                            yield '>'
                        if tag not in VOID_ELEMENTS:
                            q.append((last_container_tag, EndTag(f'</{tag}>')))
                            q.extend([(tag, child) for child in reversed(children)])
                    else:
                        yield self._stream_component_interpolation(last_container_tag, attrs, component_info)
                case TText(text_t):
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

    def static_attrs_to_str(self, attrs: tuple[tuple[str | int, ...], ...]) -> str:
        return ''.join(f' {attr[0]}' if len(attr) == 1 else f' {attr[0]}="{self.escape_html_text(attr[1])}"' for attr in attrs)

    def has_dynamic_attrs(self, attrs: tuple[tuple[str|int, ...], ...]) -> bool:
        for attr in attrs:
             match attr:
                 case [str()] | [str(), str()]:
                     continue
                 case _:
                     return True
        return False

    def extract_embedded_template(self, template: Template, start_index: int, end_index: int):
        """
        Extract the template parts exclusively from start tag to end tag.

        @TODO: "There must be a better way."
        """
        assert end_index is not None and start_index <= end_index
        # Copy the parts out of the containing template.
        index = start_index
        parts = []
        while index < end_index:
            parts.append(template.strings[index])
            if index < end_index - 1:
                parts.append(template.interpolations[index])
            index += 1
        # Now trim the first part to the end of the opening tag.
        parts[0] = parts[0][parts[0].find('>')+1:]
        # Now trim the last part (could also be the first) to the start of the closing tag.
        parts[-1] = parts[-1][:parts[-1].rfind('<')]
        return Template(*parts)


@dataclass
class RenderService:

    transform_api: TransformService

    escape_html_text: Callable = default_escape_html_text

    escape_html_comment: Callable = default_escape_html_comment

    escape_html_content_in_tag: Callable = default_escape_html_content_in_tag

    def render_template(self, template, struct_cache=None, last_container_tag=None):
        """
        Iterate left to right and pause and push new iterators when descending depth-first.

        Every interpolation becomes an iterator.

        Every iterator could return more iterators.

        The last container tag is used to determine how to handle
        text processing.  When working with fragments we might not know the
        container tag until the fragment is included at render-time.
        """
        if struct_cache is None:
            struct_cache = {}

        bf: list[str] = []
        q: list[RenderQueueItem] = []
        q.append((last_container_tag, self.walk_template(bf, template, self.process_template(template, struct_cache))))
        while q:
            last_container_tag, it = q.pop()
            for (interpolator, template, ip_info) in it:
                render_queue_item = interpolator(self, struct_cache, q, bf, last_container_tag, template, ip_info)
                if render_queue_item is not None:
                    #
                    # Pause the current iterator and push a new iterator on top of it.
                    #
                    q.append((last_container_tag, it))
                    q.append(render_queue_item)
                    break
        return ''.join(bf)

    def resolve_text_without_recursion(self, template, container_tag, content_t):
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

    def process_template(self, template, struct_cache):
        if template.strings not in struct_cache:
            struct_cache[template.strings] = self.transform_api.transform_template(template)
        return struct_cache[template.strings]

    def interpolate_attrs(self, attrs, template) -> Generator[tuple[str, object|None]]:
        """ Plug `template` values into any attribute interpolations. """
        for attr in attrs:
            match attr:
                case [str()]:
                    yield (attr[0], True)
                case [str(), str()]:
                    yield (attr[0], attr[1])
                case [str(), int()]:
                    yield (attr[0], template.interpolations[attr[1]].value)
                case [str(), str()|int(), _, *_]:
                    v_str = ''.join(part if isinstance(part, str) else str(template.interpolations[part.value].value) for part in attr[1:])
                    yield (attr[0], v_str)
                case [int()]:
                    spread_attrs = template.interpolations[attr[0]].value
                    yield from spread_attrs.items() if hasattr(spread_attrs, 'items') else spread_attrs
                case _:
                    raise ValueError(f'Unrecognized attr format {attr}')

    def resolve_attrs(self, attrs) -> dict[str, object|None]:
        new_attrs = LastUpdatedOrderedDict()
        klass = {}
        for k, v in attrs:
            match k:
                case 'class':
                    # Special cases to allow unsetting all classes.  Do we really need all over these?
                    if v is True:
                        new_attrs['class'] = v
                        klass.clear()
                    elif v is None:
                        new_attrs['class'] = None
                        klass.clear()
                    elif v == '':
                        new_attrs['class'] = ''
                        klass.clear()
                    else:
                        q = [v]
                        changes = {}
                        while q:
                            sub_v = q.pop()
                            match sub_v:
                                case str():
                                    if ' ' not in sub_v:
                                        changes[sub_v] = True
                                    else:
                                        for cn in sub_v.split():
                                            changes[cn] = True
                                case dict():
                                    for cn, enabled in sub_v.items():
                                        changes[cn] = enabled
                                case Iterable():
                                    q.extend(reversed(sub_v))
                                case None|False:
                                    pass
                                case _:
                                    raise ValueError(f'Unrecognized format for class attribute: {sub_v}')
                        if changes:
                            klass.update(changes)
                            class_str = ' '.join(cn for cn, enabled in klass.items() if enabled)
                            if class_str != new_attrs.get('class', None):
                                new_attrs['class'] = class_str
                case 'style':
                    match v:
                        case None:
                            new_attrs['style'] = None
                        case str():
                            new_attrs['style'] = v
                        case Iterable():
                            new_attrs['style'] = '; '.join(f'{pn}: {pv}' for pn, pv in (v.items() if hasattr(v, 'items') else v))
                        case _:
                            raise ValueError(f'Unrecognized format for style attribute: {v}')
                case 'aria':
                    for an, av in (v.items() if hasattr(v, 'items') else v):
                        full_name = f'aria-{an}'
                        match av:
                            case True:
                                new_attrs[full_name] = 'true'
                            case False:
                                new_attrs[full_name] = 'false'
                            case None:
                                new_attrs[full_name] = None
                            case str():
                                new_attrs[full_name] = av
                            case _:
                                new_attrs[full_name] = str(av)
                case 'data':
                    for dn, dv in (v.items() if hasattr(v, 'items') else v):
                        new_attrs[f'data-{dn}'] = dv
                case _:
                    new_attrs[k] = v
        return new_attrs

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


def render_service_factory():
    return RenderService(transform_api=TransformService())
