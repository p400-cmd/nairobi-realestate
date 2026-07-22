import asyncio
import os
import random
from datetime import datetime

import pandas as pd
from playwright.async_api import async_playwright

# CONFIGURATION

BASE_URL = "https://www.buyrentkenya.com/flats-apartments-for-sale/nairobi?sort=latest"
OUTPUT_PATH = "data/raw/listings_raw.csv"
MAX_PAGES = 150

# BROWSER SETUP

async def create_browser(playwright):
    browser = await playwright.chromium.launch(
        headless=False, slow_mo=50, channel="chrome"
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    return browser, context

EXTRACT_ALL_CARDS_JS = """
() => {
    const cards = Array.from(document.querySelectorAll('div.listing-card'));
    return cards.map(card => {
        let parsed = {};
        try {
            const xInit = card.getAttribute('x-init') || '';
            const match = xInit.match(/JSON\\.parse\\('(.*?)'\\)/);
            if (match) {
                parsed = JSON.parse(match[1]);
            }
        } catch (e) {
            parsed = {};
        }

        const q = (sel) => {
            const el = card.querySelector(sel);
            return el ? el.textContent.trim() : null;
        };

        const title = parsed.item_name
            || q('h2.font-semibold')
            || q('[data-cy="user-title"]')
            || q('h3.capitalize span.text-title');

        const priceRaw = parsed.price || parsed.itemPrice || q('[data-cy="card-price"]');

        const location = parsed.propertyArea
            || q('p.w-full.truncate.font-normal.capitalize');

        let bedrooms = null;
        if (parsed.item_category3) {
            const m = String(parsed.item_category3).match(/(\\d+)/);
            bedrooms = m ? m[1] : null;
        } else {
            bedrooms = q('[data-cy="card-bedroom_count"]');
        }

        const bathrooms = q('[data-cy="card-bathroom_count"]');

        const linkEl = card.querySelector('a[id*="listing-link"]');
        let listingUrl = null;
        if (linkEl) {
            const href = linkEl.getAttribute('href');
            listingUrl = href
                ? (href.startsWith('http') ? href : 'https://www.buyrentkenya.com' + href)
                : null;
        }

        return {
            title: title,
            price: priceRaw,
            location: location,
            bedrooms: bedrooms,
            bathrooms: bathrooms,
            listing_url: listingUrl,
            _has_title: !!title
        };
    });
}
"""


async def extract_all_cards(page):
    raw_results = await page.evaluate(EXTRACT_ALL_CARDS_JS)

    listings = []
    failed_count = 0
    for item in raw_results:
        if not item.get("_has_title"):
            failed_count += 1
            continue
        item.pop("_has_title", None)
        item["scraped_at"] = datetime.now().isoformat()
        listings.append(item)

    return listings, failed_count, len(raw_results)


# PAGE SCRAPER

async def scrape_page(page, page_number):
    url = BASE_URL if page_number == 1 else f"{BASE_URL}&page={page_number}"
    print(f"[Page {page_number}] Loading: {url}")

    try:
        await page.goto(url, timeout=90000, wait_until="domcontentloaded")
        if "no longer available" in await page.content():
            print(f"[Page {page_number}] Got 404 page. Stopping.")
            return []
    except Exception as e:
        print(f"[Page {page_number}] Failed to load: {e}")
        return []

    try:
        await page.wait_for_selector('a[class*="absolute left-0 top-0"]', timeout=30000)
        await asyncio.sleep(5)
        print(f"[Page {page_number}] Listings detected in DOM")
    except Exception:
        print(f"[Page {page_number}] Listings never appeared after waiting.")

    # Scroll slowly to trigger lazy loading of all cards
    for i in range(10):
        await page.evaluate(f"window.scrollTo(0, {i * 500})")
        await asyncio.sleep(0.5)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    # Debug snapshot
    html = await page.content()
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)

    listings, failed_count, total_found = await extract_all_cards(page)

    print(f"[Page {page_number}] Found {total_found} listing cards")
    if failed_count:
        print(
            f"[Page {page_number}] {failed_count} card(s) had no title "
            f"after JS+fallback extraction (genuine template gap, not a "
            f"staleness artifact -- these are worth inspecting if the count "
            f"is still high)"
        )
    print(f"[Page {page_number}] Successfully extracted {len(listings)} listings")

    return listings


# PAGINATION CHECK

async def has_next_page(page, current_page):
    try:
        next_page_url = f"page={current_page + 1}"
        next_btn = await page.query_selector(f'a[href*="{next_page_url}"]')
        return next_btn is not None
    except Exception:
        return False


# MAIN ORCHESTRATOR

async def scrape_all_listings(max_pages=MAX_PAGES):
    all_listings = []

    async with async_playwright() as playwright:
        browser, context = await create_browser(playwright)
        page = await context.new_page()

        for page_number in range(1, max_pages + 1):
            page_listings = await scrape_page(page, page_number)
            all_listings.extend(page_listings)

            print(f"Total collected so far: {len(all_listings)}")

            if not await has_next_page(page, page_number):
                print(f"No more pages after page {page_number}. Stopping.")
                break

            delay = random.uniform(3, 6)
            print(f"Waiting {delay:.1f}s before next page...")
            await asyncio.sleep(delay)

        await browser.close()

    if not all_listings:
        print("No listings scraped. Check selectors.")
        return None

    df = pd.DataFrame(all_listings)
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\n✓ Saved {len(df)} listings to {OUTPUT_PATH}")
    print("\nFirst 5 rows:")
    print(df.head())
    print(f"\nAll columns: {list(df.columns)}")
    print(f"\nMissing values per column:\n{df.isnull().sum()}")

    return df


# ENTRY POINT

if __name__ == "__main__":
    asyncio.run(scrape_all_listings())
