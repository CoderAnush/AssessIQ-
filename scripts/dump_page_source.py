import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto('https://online.shl.com/gb/en-us/products')
        
        try:
            await page.wait_for_selector("#myTable_wrapper", timeout=30000)
            print("Table loaded!")
        except Exception as e:
            print("Table loading timeout, dumping current state anyway...")
            
        html = await page.content()
        
        output_dir = Path("data/raw")
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "page_source.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("Dumped page source HTML to data/raw/page_source.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
