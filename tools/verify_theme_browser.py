"""Exercise the built provider UI in the installed Chrome browser."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
from threading import Thread

from playwright.sync_api import sync_playwright


def verify(browser, url, width):
    page = browser.new_page(viewport={"width": width, "height": 850}, color_scheme="dark")
    page.goto(url)
    control = page.get_by_label("Theme", exact=True)
    card = page.locator(".result-card").first
    card.wait_for()
    assert control.input_value() == "system"
    assert page.locator("html").get_attribute("data-theme") == "dark"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert card.evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(25, 38, 48)"
    assert control.bounding_box()["width"] > 0
    page.screenshot(path=f"theme-previews/dark-{width}.png")
    control.select_option("light")
    page.reload()
    card.wait_for()
    assert control.input_value() == "light"
    assert card.evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(255, 255, 255)"
    page.screenshot(path=f"theme-previews/light-{width}.png")
    toggle = page.get_by_role("button", name="Carbon Gray")
    toggle.click()
    assert toggle.get_attribute("aria-pressed") == "true"
    assert card.evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(57, 57, 57)"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=f"theme-previews/carbon-{width}.png")
    page.reload()
    card.wait_for()
    assert control.input_value() == "carbon"
    toggle.focus()
    toggle.press("Space")
    assert control.input_value() == "light"
    assert toggle.get_attribute("aria-pressed") == "false"
    control.select_option("system")
    assert page.locator("html").get_attribute("data-theme") == "dark"
    page.emulate_media(color_scheme="light")
    page.wait_for_function("document.documentElement.dataset.theme === 'light'")
    control.select_option("dark")
    page.locator("[data-card-sources]").first.click()
    page.locator("#sourceDialog[open]").wait_for()
    assert page.locator("#sourceDialog").evaluate("e => getComputedStyle(e).colorScheme") == "dark"
    page.close()
    print(f"PASS: {width}px theme, reload, OS preference, source dialog and viewport")


if __name__ == "__main__":
    handler = partial(SimpleHTTPRequestHandler, directory="_site")
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server, sync_playwright() as playwright:
        Thread(target=server.serve_forever, daemon=True).start()
        chrome = shutil.which("google-chrome") or shutil.which("chromium")
        browser = playwright.chromium.launch(executable_path=chrome)
        Path("theme-previews").mkdir(exist_ok=True)
        for width in (390, 1280):
            verify(browser, f"http://127.0.0.1:{server.server_port}", width)
        browser.close()
        server.shutdown()
