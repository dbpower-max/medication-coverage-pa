"""Exercise the built provider UI in the installed Chrome browser."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
from threading import Thread

from playwright.sync_api import sync_playwright


def verify_coverage_labels(page, width):
    query = page.get_by_role("combobox", name="Medication name")
    query.fill("lispro")
    query.press("Escape")
    vials = page.get_by_role("article").filter(
        has=page.get_by_role("heading", name="Insulin lispro 100 units/mL multidose vial", exact=True)
    )
    baseline = vials.filter(has_text="2022 baseline · presumed")
    statewide = vials.filter(has_text="AHCCCS Statewide")
    for card, scope, explanation in (
        (baseline, "2022 baseline · presumed", "Arizona Complete Health’s 2022 formulary is presumed to apply where newer evidence has not changed this product’s benefits."),
        (statewide, "AHCCCS Statewide", "AHCCCS statewide reference. Exact-plan coverage and restrictions are unverified."),
    ):
        card.get_by_text(scope, exact=True).wait_for()
        assert card.get_by_text(explanation, exact=True).count() == 0
        chips = card.locator(".chips .chip").all_text_contents()
        if scope == "2022 baseline · presumed":
            assert chips == [scope, "Covered", "Preferred", "Quantity limit"], chips
        else:
            assert {scope, "Covered", "Preferred", "Authorized generic only"}.issubset(chips), chips
        card.get_by_role("button", name="Sources").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_text(explanation, exact=True).wait_for()
        dialog.get_by_role("button", name="Close").click()

    def check_position(card):
        heading = card.get_by_role("heading").first.bounding_box()
        package = card.get_by_text("Vial size: 10 mL", exact=True).bounding_box()
        badge = card.locator(".chips .chip").first.bounding_box()
        assert abs(package["x"] - heading["x"]) < 2
        if width > 580:
            assert badge["x"] >= heading["x"] + heading["width"]
            assert abs(badge["y"] - heading["y"]) < 8
        else:
            assert badge["y"] >= package["y"] + package["height"]
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

    check_position(baseline)
    check_position(statewide)
    page.get_by_role("combobox", name="Insurance plan").fill("UnitedHealthcare")
    page.get_by_role("option", name="AHCCCS: UnitedHealthcare — AHCCCS Complete Care").click()
    exact_plan = vials.filter(has_text="UHC does not specify a preferred vial size.")
    exact_plan.get_by_text("Tier 2", exact=True).wait_for()
    assert exact_plan.get_by_text("Preferred", exact=True).is_visible()
    assert exact_plan.get_by_text("AHCCCS Statewide", exact=True).count() == 0
    check_position(exact_plan)


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
    page.get_by_role("dialog").get_by_role("button", name="Close").click()
    verify_coverage_labels(page, width)
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
