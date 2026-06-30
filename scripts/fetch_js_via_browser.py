import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def fetch_and_save(page, js_path, output_name):
    print(f"Fetching {js_path} via browser fetch...")
    try:
        js_content = await page.evaluate(f"() => fetch('{js_path}').then(r => r.text())")
        output_dir = Path("data/raw")
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / output_name, "w", encoding="utf-8") as f:
            f.write(js_content)
        print(f"Saved {output_name} (length: {len(js_content)})")
    except Exception as e:
        print(f"Error fetching {js_path}: {e}")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto('https://online.shl.com/gb/en-us/products')
        
        try:
            await page.wait_for_selector("#myTable_wrapper", timeout=30000)
            print("Table loaded! Starting fetches...")
            await fetch_and_save(page, "/scripts/js?v=CHMxBjcG4f5EwaN_Nm9iCojyYaGhZzh_3XLZrZqkcyE1", "js_lib.js")
            await fetch_and_save(page, "/scripts/sitejs?v=zSuY6hFq_0PoJ0TWAR6pTaQhPuOqSxb0c8OtQ3rdgVQ1", "site.js")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
