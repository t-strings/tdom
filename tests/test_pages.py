from playwright.sync_api import Page

def test_index(fake_page: Page):
    """Use Playwright to do a test on Hello World."""
    # Use `PWDEBUG=1` to run "headful" in the Playwright test app
    url = "http://fake/hello/index.html"
    fake_page.goto(url)
    assert fake_page.title() == "tdom"
