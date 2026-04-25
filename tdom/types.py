import typing as t
from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal
from string.templatelib import Template

from .protocols import HasHTMLDunder

type FunctionComponent = Callable[..., Template]
type FactoryComponent = Callable[..., ComponentObject]
type ComponentInterpolationValue = FunctionComponent | FactoryComponent
type ComponentObject = Callable[[], Template]


type CommonNumberType = int | float | Decimal  # fractions.Fraction? #complex?

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

type ClassAttributeValueItem = None | str
type ClassAttributeValue = (
    ClassAttributeValueItem | Sequence[ClassAttributeValueItem] | dict[str, bool]
)
type StyleAttributeValue = None | str | dict[str, str | None]
type AriaAttributeValueItem = None | object  # @TODO: Can we limit this?
type AriaAttributeValue = None | dict[str, AriaAttributeValueItem]
type DataAttributeValueItem = None | object  # @TODO: Can we limit this?
type DataAttributeValue = None | dict[str, DataAttributeValueItem]
type InterpolatedAttributeValue = None | object
type TemplatedAttributeValue = None | str | object

if t.TYPE_CHECKING:  # no native support for extra_items yet
    SpreadAttribute = t.TypedDict(
        "SpreadAttribute",
        {
            "class": t.NotRequired[ClassAttributeValue],
            "style": t.NotRequired[StyleAttributeValue],
            "aria": t.NotRequired[AriaAttributeValue],
            "data": t.NotRequired[DataAttributeValue],
        },
        extra_items=InterpolatedAttributeValue,
    )

    # @NOTE: This map is meant to be used by tooling and could potentially
    # be customized to match extensions made to the supported types.
    # @TODO: Excludes format_spec interpretations, ie. ":callback",
    # and builtin conversions, ie. "!r".
    default_template_type_map = {
        # Components
        ComponentInterpolationValue: ComponentInterpolationValue,  # <{component}></{component}>
        # Text types
        NormalTextInterpolationValue: NormalTextInterpolationValue,  # <normal_tag>{normal_text}</normal_tag>
        RawTextExactInterpolationValue: RawTextExactInterpolationValue,  # <raw_text_tag>{raw_text_exact}</raw_text_tag>
        RawTextInexactInterpolationValue: RawTextInexactInterpolationValue,  # <raw_text_tag>{raw_text_inexact} literal text and/or more {raw_text_inexact}</raw_text_tag>
        # Attribute types
        InterpolatedAttributeValue: InterpolatedAttributeValue,  # <tag standard-attribute={interpolated_attribute_value}>
        TemplatedAttributeValue: TemplatedAttributeValue,  # <tag standard-attribute="{templated_attribute_value} literal text and/or more {templated_attribute_value}">
        ClassAttributeValue: ClassAttributeValue,  # <tag class={class_attribute_value}>
        StyleAttributeValue: StyleAttributeValue,  # <tag style={style_attribute_value}>
        AriaAttributeValue: AriaAttributeValue,  # <tag aria={aria_attribute_value}>
        DataAttributeValue: DataAttributeValue,  # <tag data={data_attribute_value}>
        SpreadAttribute: SpreadAttribute,  # <tag {spread_attribute}>
    }


type StrictNormalTextInterpolationValue = (
    None
    | bool  # to support `showValue and value` idiom
    | str
    | HasHTMLDunder
    | Template
    | Iterable[StrictNormalTextInterpolationValue]
    | CommonNumberType
)

type StrictRawTextExactInterpolationValue = (
    None
    | bool  # to support `showValue and value` idiom
    | str
    | HasHTMLDunder
    | CommonNumberType
)

type StrictRawTextInexactInterpolationValue = (
    None
    | bool  # to support `showValue and value` idiom
    | str
    | CommonNumberType
)

type StrictAriaAttributeValueItem = None | (str | bool)  # @TODO: Can we limit this?
type StrictAriaAttributeValue = None | dict[str, StrictAriaAttributeValueItem]
type StrictDataAttributeValueItem = None | (
    str | bool | CommonNumberType
)  # @TODO: Can we limit this?
type StrictDataAttributeValue = None | dict[str, StrictDataAttributeValueItem]
type StrictInterpolatedAttributeValue = None | (str | CommonNumberType)
type StrictTemplatedAttributeValue = None | str | CommonNumberType
if t.TYPE_CHECKING:  # no native support for extra_items yet
    StrictSpreadAttribute = t.TypedDict(
        "StrictSpreadAttribute",
        {
            "class": t.NotRequired[ClassAttributeValue],
            "style": t.NotRequired[StyleAttributeValue],
            "aria": t.NotRequired[StrictAriaAttributeValue],
            "data": t.NotRequired[StrictDataAttributeValue],
        },
        extra_items=StrictInterpolatedAttributeValue,
    )

    # Some types can be made more strict usually by replacting `object` which
    # would normally be run through `str()` with common numbers and forcing
    # callers to cast everything else themselves with `!s` or `!r` or preformat
    # values.  Ie. To catch this t'<div>{email_server}</div>'.
    default_template_strict_type_map = default_template_type_map | {
        NormalTextInterpolationValue: StrictNormalTextInterpolationValue,
        RawTextExactInterpolationValue: StrictRawTextExactInterpolationValue,
        RawTextInexactInterpolationValue: StrictRawTextInexactInterpolationValue,
        InterpolatedAttributeValue: StrictInterpolatedAttributeValue,
        TemplatedAttributeValue: StrictTemplatedAttributeValue,
        AriaAttributeValue: StrictAriaAttributeValue,
        DataAttributeValue: StrictDataAttributeValue,
        SpreadAttribute: StrictSpreadAttribute,
    }
