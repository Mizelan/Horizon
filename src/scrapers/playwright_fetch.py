"""Standalone Playwright helper: renders a JS-heavy page and extracts article links.

Called as a subprocess by the Refetch site scraper.
Usage: python3 playwright_fetch.py <url> <timeout_ms>
"""

import json
import sys
import asyncio
from playwright.async_api import async_playwright


async def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: playwright_fetch.py <url> <timeout_ms>"}))
        sys.exit(1)

    url = sys.argv[1]
    try:
        timeout_ms = int(sys.argv[2])
    except ValueError:
        print(json.dumps({"error": "timeout_ms must be an integer"}))
        sys.exit(1)

    result = {"title": "", "articles": []}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=timeout_ms, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                page_title = await page.title()
                articles = await page.evaluate("""() => {
                    const items = [];
                    const seen = new Set();
                    document.querySelectorAll('a').forEach(a => {
                        const text = a.textContent?.trim();
                        const href = a.href;
                        if (text && text.length > 15 && href && href.startsWith('http')
                            && !href.includes('refetch.io') && !seen.has(href)) {
                            seen.add(href);
                            const parent = a.closest('[class]');
                            const dateText = parent
                                ? Array.from(parent.querySelectorAll('*'))
                                    .filter(el => el.children.length === 0)
                                    .map(el => el.textContent?.trim())
                                    .filter(Boolean)
                                    .find(t => t.match(/\\d+ (hour|day|minute|min)s? ago/))
                                : null;
                            items.push({ title: text, url: href, date_text: dateText || null });
                        }
                    });
                    return items;
                }""")

                result = {
                    "title": page_title,
                    "articles": articles[:50],
                }
            finally:
                await browser.close()
    except Exception as e:
        result = {"error": str(e)}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
