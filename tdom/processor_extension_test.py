from contextvars import ContextVar
from dataclasses import dataclass, field
from string.templatelib import Template

from .processor import (
    Attribute,
    ComponentProcessor,
    IComponentProcessor,
    IFactoryComponent,
    IFactoryMiddlewareComponent,
    IFunctionComponent,
    ProcessContext,
    TemplateProcessor,
)
from .tnodes import TAttribute


@dataclass(frozen=True, slots=True)
class AppState:
    theme_class: str


AppStateCtx: ContextVar[AppState | None] = ContextVar("AppStateCtx", default=None)


class TestComponentProcessor:
    def Body(self, children: Template) -> Template:
        return t"<body>{children}</body>"

    @dataclass
    class Header(IFactoryComponent):
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
        ) -> Template | tuple[Template, object]:
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
        assert isinstance(self.Body, IFunctionComponent)
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


ThemeCtx: ContextVar[str] = ContextVar("ThemeCtx")

ModeCtx: ContextVar[str] = ContextVar("ModeCtx")


class TestMiddlewareGetContextValues:
    @dataclass
    class ThemeProvider(IFactoryMiddlewareComponent):
        theme_name: str

        children: Template

        mode: str | None = None

        def __call__(self) -> tuple[Template, object]:
            # Hit em' with another div...
            result_t = t"<div>{self.children}</div>"
            middleware_api = self
            return result_t, middleware_api

        def get_context_values(self) -> tuple[tuple[ContextVar, str], ...]:
            context_values = ((ThemeCtx, self.theme_name),)
            if self.mode is not None:
                context_values += ((ModeCtx, self.mode),)
            return context_values

    @dataclass
    class ThemeDisplay(IFactoryComponent):
        theme_name: str

        mode: str | None = None

        def __call__(self) -> Template:
            sep = ":" if self.mode else None
            return t"<span>{self.theme_name}{sep}{self.mode}</span>"

    def _make_html(
        self, default_theme_name: str = "theme-default", default_mode: str = "mode-dark"
    ):

        tp = TemplateProcessor()

        def _html(template: Template, assume_ctx: ProcessContext | None = None):
            if assume_ctx is None:
                assume_ctx = ProcessContext()
            with ThemeCtx.set(default_theme_name), ModeCtx.set(default_mode):
                return tp.process(template, assume_ctx)

        return _html

    def _theme_name(self):
        return ThemeCtx.get()

    def _mode(self):
        return ModeCtx.get()

    def test_default(self):
        html = self._make_html()
        assert (
            html(t"<{self.ThemeDisplay} theme_name={self._theme_name:callback} />")
            == "<span>theme-default</span>"
        )

    def test_provider(self):
        html = self._make_html()
        child_t = t"<{self.ThemeDisplay} theme_name={self._theme_name:callback} />"
        assert (
            html(
                t"<{self.ThemeProvider} theme_name='theme-pycon'>{child_t}</{self.ThemeProvider}>"
            )
            == "<div><span>theme-pycon</span></div>"
        )

    def test_provider_scope(self):
        html = self._make_html()
        child_t = t"<{self.ThemeDisplay} theme_name={self._theme_name:callback} />"
        wrapped_t = t"<{self.ThemeProvider} theme_name='theme-pycon'>{child_t}</{self.ThemeProvider}>"
        assert (
            html(wrapped_t + child_t)
            == "<div><span>theme-pycon</span></div><span>theme-default</span>"
        )

    def test_two_cvars(self):
        html = self._make_html()
        child_t = t"<{self.ThemeDisplay} theme_name={self._theme_name:callback} mode={self._mode:callback} />"
        assert (
            html(
                t"<{self.ThemeProvider} theme_name='theme-pycon' mode='mode-light'>{child_t}</{self.ThemeProvider}>"
            )
            == "<div><span>theme-pycon:mode-light</span></div>"
        )
