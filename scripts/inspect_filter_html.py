import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://online.shl.com/gb/en-us/products')
        
        await asyncio.sleep(5)
        
        # Let's find any text containing 'Refine' or 'Job Level' or 'Category'
        html_snippet = await page.evaluate("""() => {
            let nodes = Array.from(document.querySelectorAll('div, form, aside, section'));
            // Find elements containing 'Job Level'
            let matches = nodes.filter(el => el.textContent.includes('Job Level') && el.children.length > 0 && el.children.length < 50);
            return matches.map(match => ({
                tagName: match.tagName,
                className: match.className,
                id: match.id,
                outerHTML: match.outerHTML
            }));
        }""")
        
        with open("data/raw/filter_structure.json", "w", encoding="utf-8") as f:
            json.dump(html_snippet, f, indent=2)
            
        print("Done!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
