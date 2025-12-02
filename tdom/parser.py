import typing as t
from string.templatelib import Template, Interpolation
from collections.abc import Iterable
from html.parser import HTMLParser

from .nodes import (
    VOID_ELEMENTS,
    TComment,
    DocumentType,
    TElement,
    TFragment,
    TNode,
    TText,
    ComponentInfo,
)
from .placeholders import (
    _placeholder as construct_placeholder,
    _find_placeholder as deconstruct_placeholder,
    placeholders_to_template,
    _FRAGMENT_TAG,
)


class NodeParser(HTMLParser):
    root: TFragment
    stack: list[TElement]
    interpolations: dict[int, Interpolation]
    active_placeholders: dict[str, int]
    template: Template
    template_string_index: int
    feeding_template_string: bool
    merge_data_text: bool

    def __init__(self, *, convert_charrefs=True, merge_data_text=True):
        self.root = TFragment(children=[])
        self.stack = []
        self.interpolations = {}
        self.active_placeholders = {}
        self.template_string_index = -1
        self.feeding_template_string = False
        self.merge_data_text = merge_data_text
        super().__init__(convert_charrefs=convert_charrefs)

    def handle_attrs(
        self, attrs_seq: t.Sequence[tuple[str, str | None]]
    ) -> tuple[tuple[str | int, ...], ...]:
        """Extract placeholders back out and prepare attrs to be stored in TElement."""
        if not self.active_placeholders:
            return tuple([(k, v) if v is not None else (k,) for k, v in attrs_seq])
        new_attrs_seq: list[tuple[str | int, ...]] = []
        for k, v in attrs_seq:
            # @NOTE: Leave key/value parts separated for error detection.
            k_parts = tuple(self.extract_template(k))
            v_parts = tuple(self.extract_template(v)) if v is not None else []
            match k_parts, v_parts:
                case [Interpolation()], []:
                    new_attrs_seq.append((k_parts[0].value,))
                case [str()], [Interpolation()]:
                    new_attrs_seq.append((k_parts[0], v_parts[0].value))
                case [str()], [str() | Interpolation(), _, *_]:
                    new_attrs_seq.append(
                        tuple(
                            [k_parts[0]]
                            + [
                                part if isinstance(part, str) else int(part.value)
                                for part in v_parts
                            ]
                        )
                    )
                case [str()], [str()]:
                    new_attrs_seq.append((k_parts[0], v_parts[0]))
                case [str()], []:
                    new_attrs_seq.append((k_parts[0],))
                case _:
                    raise ValueError(
                        f"Unupported combination of attribute name/value: {k_parts}={v_parts}"
                    )
        return tuple(new_attrs_seq)

    def handle_starttag(
        self, tag: str, attrs: t.Sequence[tuple[str, str | None]]
    ) -> None:
        element = TElement(tag, attrs=self.handle_attrs(attrs), children=[])

        tag_t = list(self.extract_template(tag, ""))
        match tag_t:
            case [Interpolation(value=starttag_ip_index)]:
                element.tag = f"component-at-{starttag_ip_index}"
                element.component_info = ComponentInfo(
                    starttag_interpolation_index=starttag_ip_index,
                    strings_slice_begin=self.get_template_part_index()[0],
                )
                if not callable(self.interpolations[starttag_ip_index].value):
                    raise TypeError("Component value should be callable.")
            case [str()]:
                pass
            case _:
                raise ValueError("Component tags should be an exact match.")

        if not self.is_void_element(element):
            self.stack.append(element)
        else:
            self.append_element_child(element)

    def handle_startendtag(
        self, tag: str, attrs: t.Sequence[tuple[str, str | None]]
    ) -> None:
        element = TElement(tag, attrs=self.handle_attrs(attrs), children=[])

        tag_t = list(self.extract_template(tag, ""))
        match tag_t:
            case [Interpolation(value=starttag_ip_index)]:
                element.tag = f"component-at-{starttag_ip_index}"
                element.component_info = ComponentInfo(
                    starttag_interpolation_index=starttag_ip_index,
                    endtag_interpolation_index=starttag_ip_index,
                )
                if not callable(self.interpolations[starttag_ip_index].value):
                    raise TypeError("Component value should be callable.")
            case [str()]:
                pass
            case _:
                raise ValueError("Component tags should be an exact match.")

        self.append_element_child(element)

    def is_void_element(self, element: TElement):
        return element.component_info is None and element.tag in VOID_ELEMENTS

    def get_ip_expression(
        self, ip_index: int, fallback_prefix: str = "interpolation-at-"
    ) -> str:
        """
        When an error occurs processing a placeholder resolve an expression to use for debugging.
        """
        ip = self.interpolations[ip_index]
        return (
            ip.expression
            if ip.expression != ""
            else f"{{{fallback_prefix}-{ip_index}}}"
        )

    def get_comp_endtag(self, endtag_ip_index: int) -> str:
        return self.get_ip_expression(
            endtag_ip_index, fallback_prefix="component-endtag-at-"
        )

    def get_comp_starttag(self, starttag_ip_index: int) -> str:
        return self.get_ip_expression(
            starttag_ip_index, fallback_prefix="component-starttag-at-"
        )

    def handle_endtag(self, tag: str) -> None:
        tag_t = list(self.extract_template(tag, ""))
        match tag_t:
            case [Interpolation(value=endtag_ip_index)]:
                # Close a component.
                if not self.stack:
                    raise ValueError(
                        f"Unexpected closing component </{self.get_comp_endtag(endtag_ip_index)}> with no open element."
                    )
                else:
                    element = self.stack.pop()
                    if element.component_info is None:
                        raise ValueError(
                            f"Mismatched closing tag </{self.get_comp_endtag(endtag_ip_index)}> for <{element.tag}>."
                        )
                    else:
                        starttag_ip_index = (
                            element.component_info.starttag_interpolation_index
                        )
                        starttag_ip = self.interpolations[starttag_ip_index]
                        endtag_ip = self.interpolations[endtag_ip_index]
                        if starttag_ip.value != endtag_ip.value:
                            raise ValueError(
                                f"Mismatched component value for <{self.get_comp_starttag(starttag_ip_index)}> and </{self.get_comp_endtag(endtag_ip_index)}>"
                            )
                        else:
                            element.component_info.endtag_interpolation_index = (
                                endtag_ip_index
                            )
                            element.component_info.strings_slice_end = (
                                self.get_template_part_index()[0]
                            )
                            self.append_element_child(element)
            case [str()]:
                # Close a regular tag.
                if not self.stack:
                    raise ValueError(
                        f"Unexpected closing tag </{tag}> with no open element."
                    )
                else:
                    element = self.stack.pop()
                    if element.component_info is not None:
                        starttag_ip_index = (
                            element.component_info.starttag_interpolation_index
                        )
                        raise ValueError(
                            f"Mismatched closing tag </{tag}> for <{self.get_comp_starttag(starttag_ip_index)}>."
                        )
                    elif element.tag != tag:
                        raise ValueError(
                            f"Mismatched closing tag </{tag}> for <{element.tag}>."
                        )
                    self.append_element_child(element)
            case _:
                raise ValueError("Component end tag must be an exact match.")

    def get_latest_text_child(self) -> TText | None:
        """Get the latest text child of the current parent or None if one does not exist."""
        children = self.get_parent().children
        if children and isinstance(children[-1], TText):
            return children[-1]
        return None

    def handle_data(self, data: str) -> None:
        text_t = self.extract_template(data)

        if self.merge_data_text:
            # Join the last template if it exists or start a new one.
            last_text_child = self.get_latest_text_child()
            if last_text_child:
                last_text_child.text_t += text_t
                return

        text = TText(text_t)
        self.append_child(text)

    def handle_comment(self, data: str) -> None:
        text_t = self.extract_template(data)
        comment = TComment(text_t)
        self.append_child(comment)

    def handle_decl(self, decl: str) -> None:
        if decl.upper().startswith("DOCTYPE"):
            doctype_content = decl[7:].strip()
            doctype = DocumentType(doctype_content)
            self.append_child(doctype)
        # For simplicity, we ignore other declarations.
        pass

    def get_parent(self) -> TFragment | TElement:
        """Return the current parent node to which new children should be added."""
        return self.stack[-1] if self.stack else self.root

    def append_element_child(self, child: TElement) -> None:
        parent = self.get_parent()
        node: TElement | TFragment = child
        # Special case: if the element is a Fragment, convert it to a Fragment node.
        if child.tag == _FRAGMENT_TAG:
            assert not child.attrs, (
                "Fragment elements should never be able to have attributes."
            )
            node = TFragment(children=child.children)
        parent.children.append(node)

    def append_child(self, child: TFragment | TText | TComment | DocumentType) -> None:
        parent = self.get_parent()
        parent.children.append(child)

    def close(self) -> None:
        if self.stack:
            raise ValueError("Invalid HTML structure: unclosed tags remain.")
        if self.active_placeholders:
            raise ValueError(
                f"Some interpolations were never found: {list(self.active_placeholders.values())}"
            )
        super().close()

    def get_node(self) -> TNode:
        """Get the Node tree parsed from the input HTML."""
        # CONSIDER: Should we invert things and offer streaming parsing?
        assert not self.active_placeholders and not self.stack, (
            "Did you forget to call close()?"
        )
        if len(self.root.children) > 1:
            # The parse structure results in multiple root elements, so we
            # return a Fragment to hold them all.
            return self.root
        elif len(self.root.children) == 1:
            # The parse structure results in a single root element, so we
            # return that element directly. This will be a non-Fragment Node.
            return self.root.children[0]
        else:
            # Special case: the parse structure is empty; we treat
            # this as an empty document fragment.
            return TFragment(children=[])

    def feed(self, data: str) -> None:
        # Special case: handle custom fragment syntax <>...</>
        # by replacing it with a unique tag name that is unlikely
        # to appear in normal HTML.
        # @TODO: These should be tracked to make sure we are unwinding them.
        data = data.replace("<>", f"<{_FRAGMENT_TAG}>").replace(
            "</>", f"</{_FRAGMENT_TAG}>"
        )
        super().feed(data)

    def feed_template(self, template: Template):
        last_index = len(template.strings) - 1
        self.template_string_index = 0
        while self.template_string_index <= last_index:
            self.feeding_template_string = True
            self.feed(template.strings[self.template_string_index])
            if self.template_string_index != last_index:
                self.feeding_template_string = False
                self.interpolations[self.template_string_index] = (
                    template.interpolations[self.template_string_index]
                )
                placeholder = construct_placeholder(self.template_string_index)
                self.active_placeholders[placeholder] = self.template_string_index
                super().feed(placeholder)
            self.template_string_index += 1

    def get_template_part_index(self):
        return self.template_string_index, 0 if self.feeding_template_string else 1

    def extract_template(self, text: str, format_spec: str = "") -> Template:
        text_t, found = placeholders_to_template(text, format_spec)
        for placeholder in found:
            if placeholder not in self.active_placeholders:
                raise ValueError(
                    f"Found unexpected placeholder {placeholder} for interpolation {deconstruct_placeholder(placeholder)}."
                )
            else:
                del self.active_placeholders[placeholder]
        return text_t

    def reset(self):
        super().reset()
        self.root = TFragment(children=[])
        self.stack.clear()
        self.interpolations.clear()
        self.active_placeholders.clear()
        self.template_string_index = -1
        self.feeding_template_string = False


def parse_html(input: str | Iterable[str] | Template) -> TNode:
    """
    Parse a string, or sequence of HTML string chunks, into a Node tree.

    If a single string is provided, it is parsed as a whole. If an iterable
    of strings is provided, each string is fed to the parser in sequence.
    This is particularly useful if you want to keep specific text chunks
    separate in the resulting Node tree.
    """
    parser = NodeParser()
    match input:
        case str():
            template = Template(input)
        case Iterable():
            template = Template(*input)
        case Template():
            template = input
    parser.feed_template(template)
    parser.close()
    return parser.get_node()
