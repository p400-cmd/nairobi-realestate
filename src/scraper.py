import asyncio
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime
import random
import os

# CONFIGURATION

BASE_URL = BASE_URL = "https://www.buyrentkenya.com/flats-apartments-for-sale"
OUTPUT_PATH = "data/raw/listings_raw.csv"
MAX_PAGES = 50

# BROWSER SETUP

async def create_browser(playwright):
    browser = await playwright.chromium.launch(
        headless=False,
        slow_mo=50,
        channel="chrome"
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    return browser, context

# DATA EXTRACTOR

async def extract_card_data(card, page):

    data = {}

    async def safe_text(selector, card):
        try:
            el = await card.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
            return None
        except Exception:
            return None

    async def safe_attr(selector, attr, card):
        try:
            el = await card.query_selector(selector)
            if el:
                return await el.get_attribute(attr)
            return None
        except Exception:
            return None

    # Title
    data['title'] = (
    await safe_text('h2.font-semibold', card) or
    await safe_text('[data-cy="user-title"]', card) or
    await safe_text('h3.capitalize span.text-title', card)
)

    # Price
    data['price'] = await safe_text('[data-cy="card-price"]', card)

    # Location
    data['location'] = await safe_text('p.w-full.truncate.font-normal.capitalize', card)

    # Bedrooms
    data['bedrooms'] = await safe_text('[data-cy="card-bedroom_count"]', card)

    # Bathrooms
    data['bathrooms'] = await safe_text('[data-cy="card-bathroom_count"]', card)

    # Listing URL
    href = await safe_attr('a[id*="listing-link"]', 'href', card)
    if href:
        data['listing_url'] = "https://www.buyrentkenya.com" + href if not href.startswith('http') else href
    else:
        data['listing_url'] = None

    data['scraped_at'] = datetime.now().isoformat()

    if not data.get('title'):
        return None

    return data

# PAGE SCRAPER

async def scrape_page(page, page_number):
    url = BASE_URL if page_number == 1 else f"{BASE_URL}?page={page_number}"
    print(f"[Page {page_number}] Loading: {url}")

    try:
        await page.goto(
            url,
            timeout=90000,
            wait_until="domcontentloaded"
        )
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

# Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)

    # Debug snapshot
    html = await page.content()
    with open("debug_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved debug_page.html")

    cards = await page.query_selector_all('div.block.flex.flex-col.justify-between.gap-y-3.overflow-hidden')

    if not cards:
        print(f"[Page {page_number}] No listing cards found.")
        return []

    print(f"[Page {page_number}] Found {len(cards)} listing cards")

    listings = []
    for card in cards:
        data = await extract_card_data(card, page)
        if data:
            listings.append(data)

    print(f"[Page {page_number}] Successfully extracted {len(listings)} listings")
    return listings

# PAGINATION CHECK

async def has_next_page(page, current_page):
    try:
        # Next page is current_page + 1
        next_page_url = f"?page={current_page + 1}"
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
    print(f"\nFirst 5 rows:")
    print(df.head())
    print(f"\nAll columns: {list(df.columns)}")
    print(f"\nMissing values per column:\n{df.isnull().sum()}")

    return df

# ENTRY POINT

if __name__ == "__main__":
    asyncio.run(scrape_all_listings())
