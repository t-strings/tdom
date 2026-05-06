import typing as t
import warnings
from collections.abc import Callable, Generator, Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from itertools import chain
from string.templatelib import Template
from types import NoneType

from .processor import (
    ProcessContext,
    TemplateProcessor,
    _substitute_spread_attrs,
    format_interpolation,
)
from .protocols import HasHTMLDunder
from .template_utils import TemplateRef
from .tnodes import (
    TAttribute,
    TComment,
    TComponent,
    TDocumentType,
    TElement,
    TFragment,
    TInterpolatedAttribute,
    TLiteralAttribute,
    TNode,
    TSpreadAttribute,
    TTemplatedAttribute,
    TText,
)

type InterpolationErrorItem = tuple[int, ValueError]


class OnErrors(StrEnum):
    IGNORE = "IGNORE"
    RAISE = "RAISE"
    WARN = "WARN"


CommonNumberTypes = (float, int, Decimal)  # AND bool because bool is subclass of int


class RuntimeType:
    pass


@dataclass(frozen=True)
class IterableOf(RuntimeType):
    """
    An iterable that must contain values that are instances of these types.
    """

    item: type | tuple[type, ...]


@dataclass(frozen=True)
class DictOf(RuntimeType):
    key: type
    value: type | tuple[type, ...]


@t.runtime_checkable
class IFunctionComponent(t.Protocol):
    __call__: Callable[..., Template]


@t.runtime_checkable
class IFactoryComponent(t.Protocol):
    __call__: Callable[..., Callable[[], Template]]


# Non-strict base type placeholders AND values.
_NormalTextInterpolationValueItem = (NoneType, str, object)
RawTextExactInterpolationValue = (NoneType, str, HasHTMLDunder, object)
RawTextInexactInterpolationValue = (NoneType, str, object)
NormalTextInterpolationValue = _NormalTextInterpolationValueItem + (
    IterableOf(_NormalTextInterpolationValueItem),
)  # Throw on generator
_ClassAttributeValueItem = (NoneType, str)
ClassAttributeValue = _ClassAttributeValueItem + (
    IterableOf(_ClassAttributeValueItem),
    DictOf(str, bool),
)
_StyleAttributeValueItem = (NoneType, str)
StyleAttributeValue = _StyleAttributeValueItem + (
    IterableOf(_StyleAttributeValueItem),
    DictOf(str, (str, NoneType)),
)
AriaAttributeValue = (NoneType, DictOf(str, (NoneType, object)))
DataAttributeValue = (NoneType, DictOf(str, (NoneType, object)))
InterpolatedAttributeValue = (NoneType, str, object)
TemplatedAttributeValueItem = (NoneType, str, object)
ComponentInterpolationValue = (IFunctionComponent, IFactoryComponent)

# Base mapping.
checked_types_map = {
    RawTextExactInterpolationValue: RawTextExactInterpolationValue,
    RawTextInexactInterpolationValue: RawTextInexactInterpolationValue,
    NormalTextInterpolationValue: RawTextInexactInterpolationValue,
    ClassAttributeValue: ClassAttributeValue,
    StyleAttributeValue: StyleAttributeValue,
    AriaAttributeValue: AriaAttributeValue,
    DataAttributeValue: DataAttributeValue,
    InterpolatedAttributeValue: InterpolatedAttributeValue,
    TemplatedAttributeValueItem: TemplatedAttributeValueItem,
    ComponentInterpolationValue: ComponentInterpolationValue,
}


_StrictNormalTextInterpolationValueItem = (
    NoneType,
    bool,
    str,
    Template,
    HasHTMLDunder,
) + CommonNumberTypes


# Mapping with more more strict variants replaced.
strict_checked_types_map = checked_types_map | {
    RawTextExactInterpolationValue: (NoneType, bool, str, HasHTMLDunder)
    + CommonNumberTypes,
    RawTextInexactInterpolationValue: (NoneType, bool, str) + CommonNumberTypes,
    NormalTextInterpolationValue: _StrictNormalTextInterpolationValueItem
    + (IterableOf(_StrictNormalTextInterpolationValueItem),),  # Throw on generator
    AriaAttributeValue: (NoneType, DictOf(str, (NoneType, str, bool))),
    DataAttributeValue: (NoneType, DictOf(str, (NoneType, str) + CommonNumberTypes)),
    InterpolatedAttributeValue: (NoneType, str) + CommonNumberTypes,
    # @NOTE: This is an item within a "subtemplate" that forms the attribute value.
    TemplatedAttributeValueItem: (NoneType, str) + CommonNumberTypes,
}


@dataclass(frozen=True)
class LintingTemplateProcessor(TemplateProcessor):
    on_errors: OnErrors = OnErrors.IGNORE

    checked_types_map: t.Mapping[tuple, tuple] = field(
        default_factory=lambda: strict_checked_types_map.copy()
    )

    def _check_tnode(
        self, template: Template, last_ctx: ProcessContext, tnode: TNode
    ) -> Sequence[InterpolationErrorItem]:
        match tnode:
            case TDocumentType(text):
                return self._check_document_type(last_ctx, text)
            case TComment(ref):
                return self._check_comment(template, last_ctx, ref)
            case TFragment(children):
                return self._check_fragment(template, last_ctx, children)
            case TComponent(start_i_index, end_i_index, attrs, children):
                return self._check_component(
                    template, last_ctx, attrs, start_i_index, end_i_index
                )
            case TElement(tag, attrs, children):
                return self._check_element(template, last_ctx, tag, attrs, children)
            case TText(ref):
                return self._check_texts(template, last_ctx, ref)
            case _:
                return [
                    (-1, ValueError(f"Unrecognized tnode: {tnode}")),
                ]

    def _check_document_type(
        self,
        last_ctx: ProcessContext,
        text: str,
    ) -> Sequence[InterpolationErrorItem]:
        return []

    def _check_value(self, value: object, checked_type: t.Any) -> bool:
        checked_types = self.checked_types_map[checked_type]
        types = tuple(t for t in checked_types if not isinstance(t, RuntimeType))
        generic_types = tuple(t for t in checked_types if isinstance(t, RuntimeType))
        if isinstance(value, types):
            return True
        for gt in generic_types:
            match gt:
                case DictOf(key=key_types, value=value_types):
                    if isinstance(value, dict):
                        for k, v in value.items():
                            if not isinstance(k, key_types) or not isinstance(
                                v, value_types
                            ):
                                return False
                        return True
                case IterableOf(item=item_types):
                    if isinstance(value, Iterable) and not isinstance(
                        value, (str, dict)
                    ):
                        # @NOTE: THESE CANNOT BE REPLAYED!!
                        if isinstance(value, Generator):
                            raise TypeError("Cannot replay generators!")
                        for i in value:
                            if not isinstance(i, item_types):
                                return False
                        return True
                case _:
                    raise TypeError("Unmatched runtime generic type.")
        return False

    def _check_text_without_recursion(
        self, template: Template, content_ref: TemplateRef
    ) -> Sequence[InterpolationErrorItem]:
        if content_ref.is_singleton:
            value = format_interpolation(
                template.interpolations[content_ref.i_indexes[0]]
            )
            if not self._check_value(value, RawTextExactInterpolationValue):
                return [
                    (
                        content_ref.i_indexes[0],
                        ValueError("Invalid raw text exact interpolation value."),
                    ),
                ]
            else:
                return []
        else:
            errors = []
            for part in content_ref:
                if isinstance(part, str):
                    continue
                value = format_interpolation(template.interpolations[part])
                if not self._check_value(value, RawTextInexactInterpolationValue):
                    errors.append(
                        (
                            part,
                            ValueError("Invalid raw text inexact interpolation value."),
                        )
                    )
            return errors

    def _check_comment(
        self,
        template: Template,
        last_ctx: ProcessContext,
        content_ref: TemplateRef,
    ) -> Sequence[InterpolationErrorItem]:
        return self._check_text_without_recursion(template, content_ref)

    def _check_fragment(
        self,
        template: Template,
        last_ctx: ProcessContext,
        children: Iterable[TNode],
    ) -> Sequence[InterpolationErrorItem]:
        return list(
            chain.from_iterable(
                self._check_tnode(template, last_ctx, tn) for tn in children
            )
        )

    def _check_component(
        self,
        template: Template,
        last_ctx: ProcessContext,
        attrs: tuple[TAttribute, ...],
        start_i_index: int,
        end_i_index: int | None,
    ) -> Sequence[InterpolationErrorItem]:
        errors = []
        # @TODO: Does it really make sense to interpret the attributes
        # without a known tag ?
        errors.extend(self._check_attrs(template, last_ctx, attrs))
        if not self._check_value(
            template.interpolations[start_i_index].value, ComponentInterpolationValue
        ):
            errors.append((start_i_index, ValueError("Invalid component callable.")))
        if (
            end_i_index is not None
            and template.interpolations[start_i_index].value
            != template.interpolations[end_i_index].value
        ):
            errors.append(
                (
                    start_i_index,
                    ValueError(
                        "Start component callable does not match end component callable."
                    ),
                )
            )
        return errors

    def _check_attr(
        self,
        name: str,
        i_index: int,
        attr_value: object,
        mode: t.Literal["interpolated", "spread"],
    ) -> Sequence[InterpolationErrorItem]:
        errors = []
        if name == "class" and not self._check_value(attr_value, ClassAttributeValue):
            errors.append(
                (i_index, ValueError(f"Invalid {mode} class attribute value"))
            )
        elif name == "style" and not self._check_value(attr_value, StyleAttributeValue):
            errors.append(
                (i_index, ValueError(f"Invalid {mode} style attribute value"))
            )
        elif name == "data" and not self._check_value(attr_value, DataAttributeValue):
            errors.append((i_index, ValueError(f"Invalid {mode} data attribute value")))
        elif name == "aria" and not self._check_value(attr_value, AriaAttributeValue):
            errors.append((i_index, ValueError(f"Invalid {mode} aria attribute value")))
        elif name not in ("class", "style", "data", "aria") and not self._check_value(
            attr_value, InterpolatedAttributeValue
        ):  # @NOTE: (Should this be/Is this) the same as spread??
            errors.append((i_index, ValueError(f"Invalid {mode} attribute value")))
        return errors

    def _check_attrs(
        self,
        template: Template,
        last_ctx: ProcessContext,
        attrs: tuple[TAttribute, ...],
    ) -> Sequence[InterpolationErrorItem]:
        """
        Check if the given attributes have valid interpolations in them.

        @NOTE: This isn't meant to catch everything at this moment but rather catch
        invalid interpolations ONLY.  One example is that a mal-formed style that is
        in a literal and is only merged because a dynamic value is found later on
        would not be "caught" with this.
        """
        errors = []
        for attr in attrs:
            match attr:
                case TLiteralAttribute(name=name, value=value):
                    # @TODO: Nothing to check for literal attributes right now.
                    pass
                case TInterpolatedAttribute(name=name, value_i_index=i_index):
                    interpolation = template.interpolations[i_index]
                    attr_value = format_interpolation(interpolation)
                    errors.extend(
                        self._check_attr(name, i_index, attr_value, mode="interpolated")
                    )
                case TTemplatedAttribute(name=name, value_ref=ref):
                    # All attributes should go through the same resolution here.
                    for i_index in ref.i_indexes:
                        value = format_interpolation(template.interpolations[i_index])
                        if not self._check_value(value, TemplatedAttributeValueItem):
                            errors.append(
                                (
                                    i_index,
                                    ValueError(
                                        "Invalid templated attribute value item"
                                    ),
                                )
                            )
                case TSpreadAttribute(i_index=i_index):
                    interpolation = template.interpolations[i_index]
                    spread_value = format_interpolation(interpolation)
                    if spread_value is None:
                        continue
                    elif not isinstance(spread_value, dict):
                        errors.append(
                            (i_index, ValueError("Invalid spread attribute value"))
                        )
                    else:
                        for sub_k, sub_v in _substitute_spread_attrs(spread_value):
                            errors.extend(
                                self._check_attr(sub_k, i_index, sub_v, mode="spread")
                            )
                case _:
                    errors.append(
                        (
                            None,
                            ValueError(
                                f"Unknown TAttribute type: {type(attr).__name__}"
                            ),
                        )
                    )
        return errors

    def _check_element(
        self,
        template: Template,
        last_ctx: ProcessContext,
        tag: str,
        attrs: tuple[TAttribute, ...],
        children: tuple[TNode, ...],
    ) -> Sequence[InterpolationErrorItem]:
        errors = []
        # @TODO: This sort of interaction might not really be maintainable.
        our_ctx = self._make_element_ctx(last_ctx, tag)
        errors.extend(self._check_attrs(template, our_ctx, attrs))
        # @TODO: This sort of interaction might not really be maintainable.
        child_ctx = self._make_child_ctx(our_ctx, tag)
        errors.extend(
            chain.from_iterable(
                self._check_tnode(template, child_ctx, tn) for tn in children
            )
        )
        return errors

    def _check_texts(
        self,
        template: Template,
        last_ctx: ProcessContext,
        ref: TemplateRef,
    ) -> Sequence[InterpolationErrorItem]:
        if last_ctx.parent_tag in ("script", "style", "title", "textarea"):
            return self._check_text_without_recursion(template, ref)
        else:
            return self._check_normal_texts(template, last_ctx, ref)

    def _check_normal_texts(
        self,
        template: Template,
        last_ctx: ProcessContext,
        ref: TemplateRef,
    ) -> Sequence[InterpolationErrorItem]:
        errors = []
        for i_index in ref.i_indexes:
            ip = template.interpolations[i_index]
            if not self._check_value(
                format_interpolation(ip), NormalTextInterpolationValue
            ):
                errors.append(
                    (i_index, ValueError("Invalid normal text interpolation value"))
                )
        return errors

    def _make_check_errors_message(
        self, template: Template, errors: Sequence[InterpolationErrorItem]
    ) -> str:
        assert errors
        parts = []
        for part_i, part_s in enumerate(template.strings[:3]):
            if part_i > 0:
                parts.append(f"{{{part_i - 1}}}")
            parts.append(part_s[:10])
        template_label = "".join(parts)
        check_errors_str = ", ".join([f"{ip_i}: {e}" for ip_i, e in errors])
        return f"Template {template_label} contains check errors: {check_errors_str}"

    def _raise_check_errors(
        self,
        template: Template,
        last_ctx: ProcessContext,
        tnode: TNode,
        errors: Sequence[InterpolationErrorItem],
    ) -> None:
        assert errors
        check_errors_message = self._make_check_errors_message(template, errors)
        raise ValueError(check_errors_message)

    def _warn_check_errors(
        self,
        template: Template,
        last_ctx: ProcessContext,
        tnode: TNode,
        errors: Sequence[InterpolationErrorItem],
    ) -> None:
        assert errors
        check_errors_message = self._make_check_errors_message(template, errors)
        warnings.warn(check_errors_message)

    def _process_template(self, template: Template, last_ctx: ProcessContext) -> str:
        root = self.parser_api.to_tnode(template)
        errors = self._check_tnode(template, last_ctx, root)
        if errors and self.on_errors:
            if self.on_errors == OnErrors.RAISE:
                self._raise_check_errors(template, last_ctx, root, errors)
            elif self.on_errors == OnErrors.WARN:
                self._warn_check_errors(template, last_ctx, root, errors)
        return super()._process_tnode(template, last_ctx, root)
