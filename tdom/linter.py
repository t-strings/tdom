import typing as t
from collections.abc import Sequence, Iterable
from dataclasses import dataclass, field
from decimal import Decimal
import warnings
from enum import StrEnum
from string.templatelib import Template

from .processor import (
    DefaultAppState,
    ProcessContext,
    RawTextExactInterpolationValue,
    RawTextInexactInterpolationValue,
    TemplateProcessor,
    format_interpolation,
)
from .protocols import HasHTMLDunder
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
from .template_utils import TemplateRef


type InterpolationErrorItem = tuple[int, ValueError]


class OnErrors(StrEnum):
    IGNORE = 'IGNORE'
    RAISE = 'RAISE'
    WARN = 'WARN'


CommonNumberTypes = (float, int, Decimal)


strict_checked_types_map = {
    RawTextExactInterpolationValue: (None, bool, str, HasHTMLDunder) + CommonNumberTypes,
    RawTextInexactInterpolationValue: (None, bool, str) + CommonNumberTypes,
    NormalTextInterpolationValue: (None, bool, str, Template, HasHTMLDunder, Iterable) + CommonNumberTypes,
}



@dataclass(frozen=True)
class LintingTemplateProcessor[T=DefaultAppState](TemplateProcessor[T]):

    on_errors: OnErrors = OnErrors.IGNORE

    checked_types_map: dict[t.TypeAliasType, tuple[type]] = field(default_factory=lambda: strict_checked_types_map.copy())

    def _check_tnode(
        self,
        template: Template,
        last_ctx: ProcessContext,
        app_state: T,
        tnode: TNode
    ) -> Sequence[InterpolationErrorItem]:
        match tnode:
            case TDocumentType(text):
                return self._check_document_type(last_ctx, app_state, text)
            case TComment(ref):
                return self._check_comment(template, last_ctx, app_state, ref)
            case TFragment(children):
                return self._check_fragment(template, last_ctx, app_state, children)
            case TComponent(start_i_index, end_i_index, attrs, children):
                return self._check_component(template, last_ctx, app_state, attrs, start_i_index, end_i_index)
            case TElement(tag, attrs, children):
                return self._check_element(template, last_ctx, app_state, tag, attrs, children)
            case TText(ref):
                return self._check_texts(template, last_ctx, app_state, ref)
            case _:
                return [(-1, ValueError(f"Unrecognized tnode: {tnode}")),]

    def _check_document_type(
        self,
        last_ctx: ProcessContext,
        app_state: T,
        text: str,
    ) -> Sequence[InterpolationErrorItem]:
        return []

    def _check_value(self, value: object, checked_type: t.Any) -> bool:
        checked_types = self.checked_types_map[checked_type]
        if value is None:
            return None in checked_types
        else:
            types = tuple(t for t in checked_types if t is not None)
            print (f'{types=}')
            return isinstance(value, types)

    def _check_text_without_recursion(self, template: Template, content_ref: TemplateRef) -> Sequence[InterpolationErrorItem]:
        if content_ref.is_singleton:
            value = format_interpolation(template.interpolations[content_ref.i_indexes[0]])
            if not self._check_value(value, RawTextExactInterpolationValue):
                return [(content_ref.i_indexes[0], ValueError('Invalid raw text exact interpolation value.')),]
            else:
                return []
        else:
            errors = []
            for part in content_ref:
                if isinstance(part, str):
                    continue
                value = format_interpolation(template.interpolations[part])
                if not self._check_value(value, RawTextInexactInterpolationValue):
                    errors.append((part, ValueError('Invalid raw text inexact interpolation value.')))
            return errors

    def _check_comment(
        self,
        template: Template,
        last_ctx: ProcessContext,
        app_state: T,
        content_ref: TemplateRef,
    ) -> Sequence[InterpolationErrorItem]:
        return self._check_text_without_recursion(template, content_ref)

    def _check_fragment(
        self,
        template: Template,
        last_ctx: ProcessContext,
        app_state: T,
        children: Iterable[TNode],
    ) -> Sequence[InterpolationErrorItem]:
        return []

    def _check_component(
        self,
        template: Template,
        last_ctx: ProcessContext,
        app_state: T,
        attrs: tuple[TAttribute, ...],
        start_i_index: int,
        end_i_index: int | None,
    ) -> Sequence[InterpolationErrorItem]:
        return []

    def _check_element(
        self,
        template: Template,
        last_ctx: ProcessContext,
        app_state: T,
        tag: str,
        attrs: tuple[TAttribute, ...],
        children: tuple[TNode, ...],
    ) -> Sequence[InterpolationErrorItem]:
        return []

    def _check_texts(
        self,
        template: Template,
        last_ctx: ProcessContext,
        app_state: T,
        ref: TemplateRef,
    ) -> Sequence[InterpolationErrorItem]:
        return []

    def _make_check_errors_message(self, template: Template, errors: Sequence[InterpolationErrorItem]) -> str:
        assert errors
        parts = []
        for part_i, part_s in enumerate(template.strings[:3]):
            if part_i > 0:
                parts.append(f'{{{part_i - 1}}}')
            parts.append(part_s[:10])
        template_label = ''.join(parts)
        check_errors_str = ', '.join([f'{ip_i}: {e}' for ip_i, e in errors])
        return f'Template {template_label} contains check errors: {check_errors_str}'

    def _raise_check_errors(self, template: Template, last_ctx: ProcessContext, app_state: T, tnode: TNode, errors: Sequence[InterpolationErrorItem]) -> None:
        assert errors
        check_errors_message = self._make_check_errors_message(template, errors)
        raise ValueError(check_errors_message)

    def _warn_check_errors(self, template: Template, last_ctx: ProcessContext, app_state: T, tnode: TNode, errors: Sequence[InterpolationErrorItem]) -> None:
        assert errors
        check_errors_message = self._make_check_errors_message(template, errors)
        warnings.warn(check_errors_message)

    def _process_tnode(
        self, template: Template, last_ctx: ProcessContext, app_state: T, tnode: TNode
    ) -> str:
        errors = self._check_tnode(template, last_ctx, app_state, tnode)
        if errors and self.on_errors:
            if self.on_errors == OnErrors.RAISE:
                self._raise_check_errors(template, last_ctx, app_state, tnode, errors)
            elif self.on_errors == OnErrors.WARN:
                self._warn_check_errors(template, last_ctx, app_state, tnode, errors)
        return super()._process_tnode(template, last_ctx, app_state, tnode)


def test_linter():
    test_t = t"<!-- {int} -->"
    tp = LintingTemplateProcessor(on_errors=OnErrors.RAISE)
    print (f'{tp.checked_types_map}')
    print (f'{tp.checked_types_map[RawTextInexactInterpolationValue]}')
    res = tp.process(test_t, assume_ctx=ProcessContext(), app_state=None)
    assert res == "<!--  -->"
