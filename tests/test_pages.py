import pytest
from playwright.sync_api import Page


# Use `PWDEBUG=1` to run "headful" in the Playwright test app
@pytest.mark.skip(reason="not implemented")
def test_hello(fake_page: Page):
    """Use Playwright to do a test on Hello World."""
    url = "http://localhost:8000/hello/index.html"
    fake_page.goto(url)
    result = "Hello World"
    output = fake_page.wait_for_selector(f"div:has-text('{result}')")
    assert output.text_content().strip() == result