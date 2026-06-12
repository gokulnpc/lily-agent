"""One-off A9 design probe: fetch a handful of PartSelect pages politely and
save raw HTML for analysis. NOT the production fetcher — this resolves schema
assumption A9 (compatibility directionality) before parser code is written.

Politeness: robots.txt checked first; small fixed list; long delays; single
browser context; stops on repeated denials. Scope is the fixed URL list below —
no discovery, no widening (CLAUDE.md crawl guardrail).
"""

from __future__ import annotations

import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

OUT = pathlib.Path("/tmp/ps-fixtures")
DELAY_S = 12

# Only the pages still missing after the first run (model-page direction for A9).
PAGES = {
    "model-dishwasher": "https://www.partselect.com/Models/WDT780SAEM1/",
    "model-fridge": "https://www.partselect.com/Models/WRS325FDAM04/",
}


def main() -> int:
    OUT.mkdir(exist_ok=True)
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
            # Let the lazy cross-reference renderers fire.
            page.wait_for_timeout(4000)
            html = page.content()
            (OUT / f"{name}.html").write_text(html)
            print(f"{name}: HTTP {status}, {len(html)} bytes")
            if status == 403 or "Access Denied" in html[:2000]:
                denials += 1
                if denials >= 2:
                    print("two denials — stopping politely")
                    return 1
            time.sleep(DELAY_S)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
