import typing as t
from contextvars import ContextVar
from dataclasses import dataclass, field
from string.templatelib import Template

from .processor import (
    Attribute,
    ComponentCallable,
    ComponentProcessor,
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


class TestComponentProcessor:
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
    class SystemComponentProcessor(IComponentProcessor):
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
            from inspect import isclass

            system_ctx = SystemCtx.get()
            if (
                system_ctx is not None
                and isclass(component_callable)
                and t.is_protocol(component_callable)
                and component_callable in system_ctx.components
            ):
                component_callable = system_ctx.components[component_callable]

            if system_ctx is not None:
                system_attrs = (("request", system_ctx.request),)
                provided_attrs = provided_attrs + system_attrs

            return self.default_component_processor_api.process(
                template=template,
                last_ctx=last_ctx,
                component_callable=component_callable,
                attrs=attrs,
                component_template=component_template,
                provided_attrs=provided_attrs,
            )

    def test_replacement(self):
        sys_comp_processor = self.SystemComponentProcessor()

        tp = TemplateProcessor(component_processor_api=sys_comp_processor)

        # Mapping established beforehand.
        components: dict[object, ComponentCallable] = {  # t.Type[t.Protocol]
            self.IHeader: self.Header,
            self.INav: self.Nav,
        }
        current_request = self.SimpleRequest(scheme="https", host="www.example.com")
        with SystemCtx.set(SystemState(components=components, request=current_request)):
            links = [("Home", "/"), ("About", "/about")]
            header_t = t"<{self.IHeader}><{self.Logo} /><{self.INav} links={links} /></{self.IHeader}>"
            assert tp.process(header_t, assume_ctx=ProcessContext()) == (
                '<div class="hdr">'
                '<span class="logo">LOGO</span>'
                '<div class="nav">'
                '<a href="https://www.example.com/">Home</a>'
                '<a href="https://www.example.com/about">About</a>'
                "</div>"
                "</div>"
            )
