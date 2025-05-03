"""Automate some testing."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page
from playwright.sync_api import Route

STUBS = Path(__file__).parent.parent.parent / "tests" / "stubs"


@dataclass
class DummyResponse:
    """Fake the Playwright ``Response`` class."""

    dummy_text: str = ""
    headers: dict[str, object] = field(
        default_factory=lambda: {"Content-Type": "text/html"}
    )
    status: int | None = None

    def text(self) -> str:
        """Fake the text method."""
        return self.dummy_text

    def body(self) -> bytes:
        """Fake the text method."""
        return bytes(self.dummy_text, "utf-8")


@dataclass
class DummyRequest:
    """Fake the Playwright ``Request`` class."""

    url: str

    @staticmethod
    def fetch(request: DummyRequest) -> DummyResponse:
        """Fake the fetch method."""
        return DummyResponse(dummy_text="URL Returned Text")


@dataclass
class DummyRoute:
    """Fake the Playwright ``Route`` class."""

    request: DummyRequest
    body: bytes | None = None
    status: str | None = None
    headers: dict[str, object] | None = None

    def fulfill(self, body: bytes, headers: dict[str, object], status: int) -> None:
        """Stub the Playwright ``route.fulfill`` method."""
        self.body = body
        self.headers = headers
        self.status = str(status)


@dataclass
class DummyPage:
    """Fake the Playwright ``Page`` class."""

    request: DummyRequest


def route_handler(page: Page, route: Route) -> None:
    """Called from the interceptor to get the data off disk."""
    this_url = urlparse(route.request.url)
    this_path = this_url.path[1:]
    is_fake = this_url.hostname == "fake"
    headers = dict()
    if is_fake:
        # We should read something from the filesystem
        this_fs_path = STUBS / this_path
        if this_fs_path.exists():
            status = 200
            mime_type = guess_type(this_fs_path)[0]
            if mime_type:
                headers = {"Content-Type": mime_type}
            body = this_fs_path.read_bytes()
        else:
            status = 404
            body = b""
    else:
        # This is to a non-fake server. Only for cases where the
        # local HTML asked for something out in the big wide world.
        response = page.request.fetch(route.request)
        status = response.status
        body = response.body()
        headers = response.headers

    route.fulfill(body=body, headers=headers, status=status)

@pytest.fixture
def fake_page(page: Page) -> Page:  # pragma: no cover
    """On the fake server, intercept and return from fs."""

    def _route_handler(route: Route) -> None:
        """Instead of doing this inline, call to a helper for easier testing."""
        route_handler(page, route)

    # Use Playwright's route method to intercept any URLs pointed at the
    # fake server and run through the interceptor instead.
    page.route("**", _route_handler)

    # Don't spend 30 seconds on timeout
    page.set_default_timeout(5000)
    return page