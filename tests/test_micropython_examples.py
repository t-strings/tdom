"""Use Playwright to test in MicroPython in a browser."""
from playwright.sync_api import Page, expect


# Use `PWDEBUG=1` to run "headful" in the Playwright test app
# @pytest.mark.skip(reason="not implemented")
def test_hello(fake_page: Page):
    """Use Playwright to do a test on Hello World."""
    url = "http://localhost:8000/index.html"
    fake_page.goto(url)
    title = fake_page.title()

    # Now wait for MicroPython to do its job
    fake_page.wait_for_selector("span:has-text('Loaded')")
    assert title == "MicroPython t-string"
    result = "Hello t-strings"
    output = fake_page.get_by_title("Example Output")
    expect(output).to_have_text(result)