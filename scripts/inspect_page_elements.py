import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://online.shl.com/gb/en-us/products')
        await asyncio.sleep(5)
        
        elements = await page.evaluate("""() => {
            const getTexts = selector => Array.from(document.querySelectorAll(selector)).map(el => el.textContent.trim()).filter(Boolean);
            return {
                h1: getTexts('h1'),
                h2: getTexts('h2'),
                h3: getTexts('h3'),
                h4: getTexts('h4'),
                buttons: getTexts('button'),
                labels: getTexts('label'),
                links: getTexts('a').slice(0, 50), // first 50 links
                body_length: document.body.outerHTML.length
            };
        }""")
        
        with open("data/raw/page_elements.json", "w", encoding="utf-8") as f:
            json.dump(elements, f, indent=2)
            
        print("Done!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
