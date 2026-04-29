from contextvars import ContextVar
from dataclasses import dataclass, field
from string.templatelib import Template

from .processor import (
    Attribute,
    ComponentProcessor,
    IComponentProcessor,
    ProcessContext,
    TemplateProcessor,
)
from .tnodes import TAttribute


@dataclass(frozen=True, slots=True)
class AppState:
    theme_class: str


AppStateCtx: ContextVar[AppState | None] = ContextVar("AppStateCtx", default=None)


class TestComponentProcessor:
    @dataclass
    class Body:
        children: Template

        def __call__(self) -> Template:
            return t"<body>{self.children}</body>"

    @dataclass
    class Header:
        children: Template

        app_state: AppState

        hdr_class: str = "hdr"

        def __call__(self) -> Template:
            return t"<div class={self.hdr_class} class={self.app_state.theme_class}>{self.children}</div>"

    @dataclass
    class AppStateComponentProcessor(IComponentProcessor):
        # Delegate to the default processor to reuse code.
        default_component_processor_api: IComponentProcessor = field(
            default_factory=ComponentProcessor
        )

        def process(
            self,
            template: Template,
            last_ctx: ProcessContext,
            component_callable: object,
            attrs: tuple[TAttribute, ...],
            component_template: Template,
            provided_attrs: tuple[Attribute, ...] = (),
        ) -> Template:
            # For now we just make the app state available to EVERY component
            # a smarter strategy would be to only include it if asked via
            # the callable's signature or even the callable's typehints.
            # But for a test this is OK.
            app_state = AppStateCtx.get()
            extended_attrs = provided_attrs + (("app_state", app_state),)
            return self.default_component_processor_api.process(
                template=template,
                last_ctx=last_ctx,
                component_callable=component_callable,
                attrs=attrs,
                component_template=component_template,
                provided_attrs=extended_attrs,
            )

    def _make_html(self):
        app_state_processor = self.AppStateComponentProcessor()
        tp = TemplateProcessor(component_processor_api=app_state_processor)
        assume_ctx = ProcessContext()

        def _html(template: Template, app_state: AppState | None = None) -> str:
            if app_state is None:
                app_state = AppState(theme_class="theme-default")
            with AppStateCtx.set(app_state):
                return tp.process(template, assume_ctx=assume_ctx)

        return _html

    def test_injected_app_state(self):
        name = "App"
        body_t = (
            t"<{self.Body}><{self.Header}><h1>{name}</h1></{self.Header}></{self.Body}>"
        )
        html = self._make_html()
        assert (
            html(body_t, app_state=None)
            == '<body><div class="hdr theme-default"><h1>App</h1></div></body>'
        )
        assert (
            html(body_t, app_state=AppState(theme_class="theme-spring"))
            == '<body><div class="hdr theme-spring"><h1>App</h1></div></body>'
        )
        assert (
            html(body_t, app_state=None)
            == '<body><div class="hdr theme-default"><h1>App</h1></div></body>'
        )
