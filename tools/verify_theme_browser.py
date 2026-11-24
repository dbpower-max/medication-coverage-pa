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

# One-time beta run against the published provider site.
if __name__ == "__main__":
    import re
    from playwright.sync_api import expect
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=shutil.which("google-chrome"))
        cases = [("Arizona Complete", "Acamprosate", "statewide reference"), ("Banner", "Adderall XR", "50 per 90 days"), ("UnitedHealthcare|UHC", "Butrans", "Tier 2")]
        for width in (360, 412, 1280):
            page = browser.new_page(viewport={"width": width, "height": 840}, has_touch=width<500)
            page.goto("https://dbpower-max.github.io/medication-coverage-pa/")
            for plan, medication, qualifier in cases:
                page.get_by_role("button", name="Show insurance plan options").click()
                page.get_by_role("option", name=re.compile(plan,re.I)).click()
                search = page.get_by_role("combobox",name="Medication name")
                search.fill(medication)
                search.press("Escape")
                card = page.locator("article").filter(has=page.get_by_role("heading", name=re.compile(medication,re.I))).filter(has_text=re.compile(qualifier,re.I)).first
                expect(card).to_contain_text(re.compile(qualifier,re.I))
                card.get_by_role("button",name="Sources",exact=True).click()
                modal = page.get_by_role("dialog")
                expect(modal).to_be_visible()
                links = modal.locator('a[href*="#page="]:visible')
                links.first.wait_for()
                targets = links.evaluate_all("items => items.map(a=>a.href)")
                assert all(re.search(r"#page=[1-9][0-9]*$", u) for u in targets), targets
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert modal.evaluate("d=>d.getBoundingClientRect().right <= innerWidth")
                target = {"Acamprosate":"ahcccs-drug-list-2026-11-01.pdf#page=3", "Adderall XR":"bufc_formulary_eff10012026_en.pdf#page=1", "Butrans":"uhc-az-medicaid-pdl-2026-10-01.pdf#page=202"}[medication]
                assert any(u.endswith(target) for u in targets), targets
                with page.expect_popup() as opened:
                    modal.locator('a[href*="'+target+'"]:visible').first.click()
                dest = opened.value
                dest.wait_for_load_state("commit")
                print("BETA",width,plan,medication,targets,"clicked",dest.url,flush=True)
                dest.close()
                modal.get_by_role("button",name="Close").click()
                expect(modal).not_to_be_visible()
            page.close()
        browser.close()
