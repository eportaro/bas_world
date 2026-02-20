"""
BAS World Truck Image Scraper v2
=================================
Uses Selenium to navigate basworld.com, extract the real CDN image URLs
from the Next.js _next/image proxy, and download high-res truck photos.

Usage:
    pip install selenium webdriver-manager requests
    python scrape_images.py

Strategy:
1. Open each brand page with Selenium (bypasses 403 / Cloudflare)
2. Find all <img> elements whose src contains "static.basworld.com"
   (BAS World stores truck photos on their static CDN)
3. Extract the raw CDN URL from the _next/image proxy URL
4. Download directly from static.basworld.com
5. As a fallback, take Selenium-based screenshots of truck card elements
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.basworld.com/stock/tractorhead"
BRANDS = ["daf", "scania", "mercedes", "volvo", "man", "renault", "iveco", "ford"]
OUTPUT_DIR = Path(__file__).parent / "frontend" / "images"
MAP_FILE = OUTPUT_DIR / "image_map.json"
MAX_IMAGES_PER_BRAND = 5
SCROLL_PAUSE = 2
PAGE_LOAD_WAIT = 10


def create_driver():
    """Create a headless Chrome WebDriver with realistic browser settings."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    # Don't block images — we need them rendered
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    # Remove webdriver flag to avoid detection
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def scroll_to_load(driver, max_scrolls=5):
    """Scroll to trigger lazy-loaded images and wait for them."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    for i in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    # Scroll back to top slowly to trigger any remaining lazy loads
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)


def extract_cdn_url(src):
    """Extract the raw static.basworld.com CDN URL from a _next/image proxy URL.

    Example input:
      https://www.basworld.com/_next/image?url=https%3A%2F%2Fstatic.basworld.com%2F
      photos%2Fvehicle%2Fworld%2F1080%2Fused-Trekker-Scania-S520-4X2-2019_355534.jpg&w=1080&q=75

    Returns:
      https://static.basworld.com/photos/vehicle/world/1080/used-Trekker-Scania-S520-4X2-2019_355534.jpg
    """
    if "_next/image" in src:
        parsed = urlparse(src)
        params = parse_qs(parsed.query)
        if "url" in params:
            return unquote(params["url"][0])
    return src


def extract_truck_images(driver, brand):
    """Find actual truck photo URLs from the current page.

    BAS World uses Next.js with _next/image proxy. The real photos live at
    static.basworld.com/photos/vehicle/...

    We look for:
    1. img[src*="static.basworld.com"] — directly embedded (rare)
    2. img[src*="_next/image"] where the url param contains "static.basworld.com"
    3. Any img with "vehicle" or "Trekker" in the URL
    """
    urls = []
    seen = set()

    # Wait for images to load
    time.sleep(3)

    # Get ALL img elements
    img_elements = driver.find_elements(By.TAG_NAME, "img")
    print(f"  📋 Found {len(img_elements)} total <img> elements on page")

    for img in img_elements:
        src = img.get_attribute("src") or ""
        data_src = img.get_attribute("data-src") or ""
        srcset = img.get_attribute("srcset") or ""

        # Check all source attributes
        for raw_url in [src, data_src] + srcset.split(","):
            raw_url = raw_url.strip().split(" ")[0]  # Remove srcset size hints
            if not raw_url:
                continue

            # Extract CDN URL if it's a _next/image proxy
            cdn_url = extract_cdn_url(raw_url)

            # Only keep truck-related images from the CDN
            is_truck = (
                "static.basworld.com/photos/vehicle" in cdn_url
                or "static.basworld.com/photos" in cdn_url
                or ("Trekker" in cdn_url and "static.basworld.com" in cdn_url)
            )

            if is_truck and cdn_url not in seen:
                seen.add(cdn_url)
                urls.append(cdn_url)

    # Also try to find images via source elements inside <picture> tags
    picture_sources = driver.find_elements(By.CSS_SELECTOR, "picture source")
    for src_el in picture_sources:
        srcset = src_el.get_attribute("srcset") or ""
        for part in srcset.split(","):
            raw_url = part.strip().split(" ")[0]
            cdn_url = extract_cdn_url(raw_url)
            if "static.basworld.com/photos/vehicle" in cdn_url and cdn_url not in seen:
                seen.add(cdn_url)
                urls.append(cdn_url)

    # Also check for background images in style attributes
    elements_with_bg = driver.find_elements(By.CSS_SELECTOR, "[style*='background']")
    for el in elements_with_bg:
        style = el.get_attribute("style") or ""
        found_urls = re.findall(r"url\(['\"]?(https?://[^'\")\s]+)['\"]?\)", style)
        for u in found_urls:
            cdn_url = extract_cdn_url(u)
            if "static.basworld.com/photos/vehicle" in cdn_url and cdn_url not in seen:
                seen.add(cdn_url)
                urls.append(cdn_url)

    return urls


def download_image(url, filepath):
    """Download truck image from static.basworld.com CDN."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.basworld.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        r = requests.get(url, headers=headers, timeout=20, stream=True)
        r.raise_for_status()

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        size_kb = filepath.stat().st_size / 1024
        if size_kb < 5:  # Skip tiny files (likely error pages)
            filepath.unlink()
            print(f"  ⚠ Too small ({size_kb:.0f} KB), removed: {filepath.name}")
            return False

        print(f"  ✅ Downloaded ({size_kb:.0f} KB): {filepath.name}")
        return True

    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


def screenshot_vehicle_cards(driver, brand, brand_dir, max_cards=5):
    """Fallback: screenshot individual vehicle card elements from the page."""
    print(f"  📸 Trying screenshot fallback for {brand}...")
    saved = []

    # Common CSS selectors for vehicle cards on auto dealer sites
    card_selectors = [
        "a[href*='/stock/'] img",
        "[class*='vehicle'] img",
        "[class*='card'] img",
        "[class*='listing'] img",
        "[data-testid*='vehicle'] img",
        "article img",
    ]

    for selector in card_selectors:
        try:
            card_imgs = driver.find_elements(By.CSS_SELECTOR, selector)
            if not card_imgs:
                continue

            print(f"  Found {len(card_imgs)} images with selector: {selector}")

            count = 0
            for i, img in enumerate(card_imgs[:max_cards * 2]):
                # Skip tiny images (logos, icons)
                try:
                    width = img.size.get("width", 0)
                    height = img.size.get("height", 0)
                    if width < 100 or height < 80:
                        continue
                except:
                    continue

                filepath = brand_dir / f"{brand}_screenshot_{count + 1}.png"
                try:
                    # Scroll element into view
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
                    time.sleep(0.5)
                    img.screenshot(str(filepath))

                    size_kb = filepath.stat().st_size / 1024
                    if size_kb < 3:
                        filepath.unlink()
                        continue

                    print(f"  📸 Screenshot ({size_kb:.0f} KB): {filepath.name}")
                    saved.append({
                        "brand": brand.upper(),
                        "index": count + 1,
                        "filename": filepath.name,
                        "source_url": "screenshot",
                        "local_path": f"images/{brand.upper()}/{filepath.name}",
                    })
                    count += 1
                    if count >= max_cards:
                        break
                except Exception as e:
                    continue

            if saved:
                break  # Found images with this selector

        except Exception:
            continue

    return saved


def scrape_brand(driver, brand):
    """Scrape truck images for a single brand."""
    url = f"{BASE_URL}/{brand}"
    print(f"\n{'='*60}")
    print(f"🔍 Scraping: {url}")
    print(f"{'='*60}")

    try:
        driver.get(url)

        # Wait for page to fully load
        WebDriverWait(driver, PAGE_LOAD_WAIT).until(
            EC.presence_of_element_located((By.TAG_NAME, "img"))
        )
        time.sleep(5)  # Extra wait for Next.js hydration + image loading

        # Scroll to trigger lazy loads
        scroll_to_load(driver, max_scrolls=5)

        # Wait for images to fully render
        time.sleep(3)

        # Extract truck image CDN URLs
        image_urls = extract_truck_images(driver, brand)
        print(f"  🔗 Found {len(image_urls)} truck image CDN URLs")

        if image_urls:
            for u in image_urls[:3]:
                print(f"     → {u[:100]}...")

        # Download images
        brand_dir = OUTPUT_DIR / brand.upper()
        brand_dir.mkdir(parents=True, exist_ok=True)
        saved = []

        for i, img_url in enumerate(image_urls[:MAX_IMAGES_PER_BRAND]):
            ext = ".jpg"
            for e in [".png", ".webp"]:
                if e in img_url.lower():
                    ext = e
                    break

            filename = f"{brand}_{i + 1}{ext}"
            filepath = brand_dir / filename

            if download_image(img_url, filepath):
                saved.append({
                    "brand": brand.upper(),
                    "index": i + 1,
                    "filename": filename,
                    "source_url": img_url,
                    "local_path": f"images/{brand.upper()}/{filename}",
                })

        # Fallback: if no CDN downloads worked, try screenshots
        if not saved:
            print(f"  ⚠ No CDN images downloaded, trying screenshot fallback...")
            saved = screenshot_vehicle_cards(driver, brand, brand_dir)

        print(f"  📦 Total saved: {len(saved)} images for {brand.upper()}")
        return saved

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    """Main entry point."""
    print("🚛 BAS World Truck Image Scraper v2")
    print("=" * 60)
    print(f"Output: {OUTPUT_DIR}")
    print(f"Brands: {', '.join(b.upper() for b in BRANDS)}")
    print(f"Max per brand: {MAX_IMAGES_PER_BRAND}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up old bad images
    for d in OUTPUT_DIR.iterdir():
        if d.is_dir() and d.name in [b.upper() for b in BRANDS]:
            for f in d.iterdir():
                if f.stat().st_size < 5000:  # Remove files < 5KB (likely garbage)
                    f.unlink()
                    print(f"  🗑 Removed old bad image: {f}")

    print("🔧 Starting Chrome WebDriver...")
    try:
        driver = create_driver()
    except Exception as e:
        print(f"❌ Failed to start Chrome: {e}")
        print("  Make sure Google Chrome is installed.")
        print("  Install: pip install selenium webdriver-manager requests")
        sys.exit(1)

    image_map = {}
    total_saved = 0

    try:
        for brand in BRANDS:
            saved = scrape_brand(driver, brand)
            if saved:
                image_map[brand.upper()] = saved
                total_saved += len(saved)
    finally:
        driver.quit()
        print("\n🔒 Browser closed")

    # Save image map
    with open(MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(image_map, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"✅ DONE! Scraped {total_saved} images across {len(image_map)} brands")
    print(f"📁 Images: {OUTPUT_DIR}")
    print(f"📋 Map: {MAP_FILE}")
    print(f"{'='*60}")

    if total_saved == 0:
        print("\n⚠ No images were downloaded.")
        print("  BAS World may block automated access.")
        print("  Try running without --headless to debug.")


if __name__ == "__main__":
    main()
