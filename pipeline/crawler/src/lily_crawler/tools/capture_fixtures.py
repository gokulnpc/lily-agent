"""Capture real PartSelect pages as parser test + drift-baseline fixtures.

Run manually when refreshing fixtures (e.g. after a markup change). NOT part of
the automated crawl — it's a developer utility. Politeness still applies: small
fixed list, long delays, robots-allowed paths only, stops on repeated denials.

Headless Chromium and plain HTTP are Akamai-403'd; this drives the real Chrome
channel, same as the production fetcher.

    uv run python -m lily_crawler.tools.capture_fixtures

Writes into pipeline/parsers/tests/fixtures/. Keep the captured HTML in git: it
is both the parser unit-test corpus and the schema-drift baseline.
"""

from __future__ import annotations

import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

# tools/ → lily_crawler → src → crawler → pipeline
FIXTURES = pathlib.Path(__file__).resolve().parents[4] / "parsers" / "tests" / "fixtures"
DELAY_S = 12

# One of each page type the parsers handle, plus robots for the politeness test.
PAGES = {
    "robots": "https://www.partselect.com/robots.txt",
    "part-fridge": "https://www.partselect.com/PS11752778-Whirlpool-WPW10321304-Refrigerator-Door-Shelf-Bin.htm",
    "part-dishwasher": "https://www.partselect.com/PS11746591-Whirlpool-WPW10348269-Dishwasher-Door-Balance-Link-Kit.htm",
    "model-fridge": "https://www.partselect.com/Models/WRS325FDAM04/",
    "model-dishwasher": "https://www.partselect.com/Models/WDT780SAEM1/",
    "repair-index-fridge": "https://www.partselect.com/Repair/Refrigerator/",
    "symptom-fridge": "https://www.partselect.com/Repair/Refrigerator/Door-Sweating/",
}


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    denials = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = context.new_page()
        for name, url in PAGES.items():
            response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            status = response.status if response else 0
            page.wait_for_timeout(4000)  # let lazy cross-reference renderers fire
            html = page.content()
            if status == 403 or "Access Denied" in html[:2000]:
                denials += 1
                print(f"{name}: HTTP {status} DENIED (not saved)")
                if denials >= 2:
                    print("two denials — stopping politely")
                    return 1
                continue
            (FIXTURES / f"{name}.html").write_text(html)
            print(f"{name}: HTTP {status}, {len(html)} bytes -> {name}.html")
            time.sleep(DELAY_S)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
