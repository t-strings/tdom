import typing as t
from contextvars import ContextVar
from dataclasses import dataclass, field
from string.templatelib import Template

from .processor import (
    Attribute,
    ComponentCallable,
    ComponentObject,
    ComponentProcessor,
    DefaultAppState,
    IComponentProcessor,
    ProcessContext,
    TemplateProcessor,
)
from .tnodes import TAttribute


class ISimpleRequest(t.Protocol):
    def make_url(self, path: str) -> str: ...


@dataclass()
class SystemState:
    request: ISimpleRequest
    components: dict[object, ComponentCallable] = field(
        default_factory=dict
    )  # t.Type[t.Protocol]


SystemCtx: ContextVar[SystemState | None] = ContextVar("SystemCtx", default=None)


class TestContextVarIntegration:
    @dataclass
    class SimpleRequest(ISimpleRequest):
        scheme: str
        host: str

        def make_url(self, path: str) -> str:
            # @NOTE: Don't actually make URLs this way, this is just an example.
            return f"{self.scheme}://{self.host}/{path.lstrip('/')}"

    class IHeader(t.Protocol):
        children: Template
        hdr_class: str

        def __call__(self) -> Template: ...

    @dataclass
    class Header(IHeader):
        children: Template

        hdr_class: str = "hdr"

        def __call__(self) -> Template:
            return t"<div class={self.hdr_class}>{self.children}</div>"

    class INav(t.Protocol):
        request: ISimpleRequest

        links: tuple[tuple[str, str], ...]

        def __call__(self) -> Template: ...

    @dataclass
    class Nav(INav):
        request: ISimpleRequest

        links: tuple[tuple[str, str], ...] = ()

        nav_class: str = "nav"

        def _make_nav_links(self) -> list[Template]:
            return [
                t"<a href={self.request.make_url(href)}>{label}</a>"
                for label, href in self.links
            ]

        def __call__(self) -> Template:
            return t"<div class={self.nav_class}>{self._make_nav_links()}</div>"

    @dataclass
    class Logo:  # NO DI / NO Protocol
        logo_fallback: str = "LOGO"

        logo_class: str = "logo"

        def __call__(self) -> Template:
            return t"<span class={self.logo_class}>{self.logo_fallback}</span>"

    @dataclass
    class SystemComponentProcessor[T = DefaultAppState](IComponentProcessor[T]):
        default_component_processor_api: IComponentProcessor[T] = field(
            default_factory=ComponentProcessor[T]
        )

        def process(
            self,
            template: Template,
            last_ctx: ProcessContext,
            app_state: T,
            component_callable: object,
            attrs: tuple[TAttribute, ...],
            component_template: Template,
            provided_attrs: tuple[Attribute, ...] = (),
        ) -> tuple[Template, ComponentObject | None]:
            from inspect import isclass

            system_ctx = SystemCtx.get()
            if (
                system_ctx is not None
                and isclass(component_callable)
                and t.is_protocol(component_callable)
                and component_callable in system_ctx.components
            ):
                # Use the protocol to get the concrete component factory.
                # @NOTE: This is using the contextvars.ContextVar to
                # get this information but maybe in the future we'd have
                # a way to get ctx directly from a parameter.
                component_callable = system_ctx.components[component_callable]

            # Also pass in system provided attributes to EVERY
            # component (but it will only be used during the call if it needed.
            # @NOTE: This is using the contextvars.ContextVar to
            # get this information but maybe in the future we'd have
            # a way to get ctx directly from a parameter.
            if system_ctx is not None:
                system_attrs = (("request", system_ctx.request),)
                provided_attrs = provided_attrs + system_attrs

            # @NOTE: We mostly just put the correct values in the right places
            # to perform the default component processing.
            # - `component_callable` is now the actual concrete implementation
            # - `provided_attrs` now has attrs that might not be in the template
            # So we can just wrap the default processor and let it do all the
            # work. BUT... if we wanted to just replace the invocation we could
            # do that and just return the correct thing ourselves.
            return self.default_component_processor_api.process(
                template=template,
                last_ctx=last_ctx,
                app_state=app_state,
                component_callable=component_callable,
                attrs=attrs,
                component_template=component_template,
                provided_attrs=provided_attrs,
            )

    def _make_html(self) -> t.Callable[[Template], str]:
        tp = TemplateProcessor(component_processor_api=self.SystemComponentProcessor())
        assume_ctx = ProcessContext()

        def _html(t: Template) -> str:
            # @NOTE: This integration does not really use app state.
            return tp.process(t, assume_ctx=assume_ctx, app_state={})

        return _html

    def test_dynamic_component_callable_resolution_and_dynamic_component_kwargs(self):
        html = self._make_html()
        # Mapping established beforehand.
        components: dict[object, ComponentCallable] = {  # t.Type[t.Protocol]
            self.IHeader: self.Header,
            self.INav: self.Nav,
        }
        current_request = self.SimpleRequest(scheme="https", host="www.example.com")
        with SystemCtx.set(SystemState(components=components, request=current_request)):
            links = [("Home", "/"), ("About", "/about")]
            header_t = t"<{self.IHeader}><{self.Logo} /><{self.INav} links={links} /></{self.IHeader}>"
            assert html(header_t) == (
                '<div class="hdr">'
                '<span class="logo">LOGO</span>'
                '<div class="nav">'
                '<a href="https://www.example.com/">Home</a>'
                '<a href="https://www.example.com/about">About</a>'
                "</div>"
                "</div>"
            )


@dataclass
class AuthStatus:
    """
    Component factory that shows authentication status.

    app_logged_in:
        True if the user is logged in, otherwise False.
    classes:
        Tuple of css classes to apply to the wrapping element.
    """

    app_logged_in: bool = False

    classes: tuple[str, ...] = ("auth-display",)

    def __call__(self) -> Template:
        status_msg = "Logged In" if self.app_logged_in else "Logged Out"
        return t"<span class={self.classes}>{status_msg}</span>"


AppLoggedInCtx = ContextVar("AppLoggedInCtx", default=False)


class TestSimpleContextVarIntegration:
    def _make_html(self) -> t.Callable[[Template], str]:
        # @NOTE: This integration does not use a component processor at all.
        tp = TemplateProcessor()
        assume_ctx = ProcessContext()

        def _html(t: Template) -> str:
            # @NOTE: This integration does not really use app state.
            return tp.process(t, assume_ctx=assume_ctx, app_state={})

        return _html

    def test_inject_kwargs_with_cvar(self):
        html = self._make_html()

        def get_app_logged_in() -> bool:
            return AppLoggedInCtx.get()

        # @NOTE: This does not call the function immediately but rather it is called
        # only when the template is processed.
        test_t = (
            t"<div><{AuthStatus} app_logged_in={get_app_logged_in:callback} /></div>"
        )
        with AppLoggedInCtx.set(True):
            res = html(test_t)
            assert res == '<div><span class="auth-display">Logged In</span></div>'
        with AppLoggedInCtx.set(False):
            res = html(test_t)
            assert res == '<div><span class="auth-display">Logged Out</span></div>'


class TestAppStateIntegration:
    @dataclass
    class AppStateComponentProcessor(IComponentProcessor[DefaultAppState]):
        default_component_processor_api: IComponentProcessor[DefaultAppState] = field(
            default_factory=ComponentProcessor[DefaultAppState]
        )

        def process(
            self,
            template: Template,
            last_ctx: ProcessContext,
            app_state: DefaultAppState,
            component_callable: object,
            attrs: tuple[TAttribute, ...],
            component_template: Template,
            provided_attrs: tuple[Attribute, ...] = (),
        ) -> tuple[Template, ComponentObject | None]:
            provided_attrs = provided_attrs + (
                ("app_logged_in", app_state.get("app_logged_in", False)),
            )
            return self.default_component_processor_api.process(
                template=template,
                last_ctx=last_ctx,
                app_state=app_state,
                component_callable=component_callable,
                attrs=attrs,
                component_template=component_template,
                provided_attrs=provided_attrs,
            )

    def _make_html(self) -> t.Callable[[Template, DefaultAppState], str]:
        tp = TemplateProcessor(
            component_processor_api=self.AppStateComponentProcessor()
        )
        assume_ctx = ProcessContext()

        def _html(t: Template, app_state: DefaultAppState) -> str:
            return tp.process(t, assume_ctx=assume_ctx, app_state=app_state)

        return _html

    def test_injecting_app_state_into_component_kwargs(self):
        html = self._make_html()
        res = html(
            t"<div><{AuthStatus} /></div>",
            {"app_logged_in": True},
        )
        assert res == '<div><span class="auth-display">Logged In</span></div>'
        auth_cls = "auth-status"
        res = html(
            t"<div><{AuthStatus} classes={(auth_cls,)} /></div>",
            {"app_logged_in": False},
        )
        assert res == '<div><span class="auth-status">Logged Out</span></div>'


@dataclass
class AppState:
    """
    Well defined application state that is created on every request
    and provided to components via a custom component processor.
    """

    logged_in: bool = False


class TestTypedAppStateIntegration:
    @dataclass
    class TypedAppStateComponentProcessor(IComponentProcessor[AppState]):
        default_component_processor_api: IComponentProcessor[AppState] = field(
            default_factory=ComponentProcessor[AppState]
        )

        def process(
            self,
            template: Template,
            last_ctx: ProcessContext,
            app_state: AppState,
            component_callable: object,
            attrs: tuple[TAttribute, ...],
            component_template: Template,
            provided_attrs: tuple[Attribute, ...] = (),
        ) -> tuple[Template, ComponentObject | None]:
            provided_attrs = provided_attrs + (("app_logged_in", app_state.logged_in),)
            return self.default_component_processor_api.process(
                template=template,
                last_ctx=last_ctx,
                app_state=app_state,
                component_callable=component_callable,
                attrs=attrs,
                component_template=component_template,
                provided_attrs=provided_attrs,
            )

    def _make_html(self) -> t.Callable[[Template, AppState], str]:
        tp = TemplateProcessor(
            component_processor_api=self.TypedAppStateComponentProcessor()
        )
        assume_ctx = ProcessContext()

        def _html(t: Template, app_state: AppState) -> str:
            return tp.process(t, assume_ctx=assume_ctx, app_state=app_state)

        return _html

    def test_injecting_typed_app_state_into_component_kwargs(self):
        html = self._make_html()
        res = html(
            t"<div><{AuthStatus} /></div>",
            AppState(logged_in=True),
        )
        assert res == '<div><span class="auth-display">Logged In</span></div>'
        auth_cls = "auth-status"
        res = html(
            t"<div><{AuthStatus} classes={(auth_cls,)} /></div>",
            AppState(logged_in=False),
        )
        assert res == '<div><span class="auth-status">Logged Out</span></div>'

    def test_local_precedence(self):
        html = self._make_html()
        global_logged_in = False
        local_logged_in = True
        res = html(
            t"<div><{AuthStatus} { {'app_logged_in': local_logged_in} } /></div>",
            AppState(logged_in=global_logged_in),
        )
        assert res == '<div><span class="auth-display">Logged In</span></div>'
