"""Use Playwright to test examples in MicroPython in a browser."""

import pytest
from playwright.sync_api import Page


# Use `PWDEBUG=1` to run "headful" in the Playwright test app
# @pytest.mark.skip(reason="not implemented")
def test_static_string(fake_page: Page, assert_no_console_errors):
    url = "http://localhost:8000/index.html"
    fake_page.goto(url)

    # First check for errors in the console
    title = fake_page.title()
    assert title == "MicroPython t-string"

    # Now wait for MicroPython to do its job
    fake_page.wait_for_selector("span:has-text('Loaded')")

    # See if the first result evaluated to what was expected
    first_section = fake_page.get_by_title("static_string.string_literal")
    first_result = first_section.get_by_title("result")
    first_inner_html = first_result.inner_html()
    assert first_inner_html == "Hello World"
