import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Load local file
        local_path = Path("data/raw/page_source.html").absolute()
        url = f"file:///{local_path.as_posix()}"
        print(f"Loading local URL: {url}")
        await page.goto(url)
        
        # Analyze accordion and filter panels
        filter_data = await page.evaluate("""() => {
            const result = {};
            
            // Look for any headers or divs that might be accordion panels
            const panels = [];
            document.querySelectorAll('div, h1, h2, h3, h4, h5, h6, button, a').forEach(el => {
                const text = el.textContent.trim();
                if (text && (text.includes('Job Level') || text.includes('Category') || text.includes('Product Group') || text.includes('Proposition') || text.includes('Refine'))) {
                    panels.push({
                        tagName: el.tagName,
                        className: el.className,
                        id: el.id,
                        text: text.substring(0, 100),
                        parentTagName: el.parentElement ? el.parentElement.tagName : ''
                    });
                }
            });
            result.panels = panels;
            
            // Find all input and select elements
            const inputs = [];
            document.querySelectorAll('input, select').forEach(el => {
                inputs.push({
                    tagName: el.tagName,
                    type: el.type,
                    name: el.name,
                    id: el.id,
                    value: el.value,
                    className: el.className
                });
            });
            result.inputs = inputs;
            
            // Check if there are any lists or divs with options
            const optionLists = [];
            document.querySelectorAll('ul, ol, div').forEach(el => {
                const text = el.textContent.trim();
                if (el.children.length > 2 && (text.includes('Graduate') || text.includes('Director') || text.includes('Professional') || text.includes('Manager'))) {
                    optionLists.push({
                        tagName: el.tagName,
                        className: el.className,
                        id: el.id,
                        htmlSnippet: el.outerHTML.substring(0, 1000)
                    });
                }
            });
            result.optionLists = optionLists;
            
            return result;
        }""")
        
        with open("data/raw/parsed_dom_analysis.json", "w", encoding="utf-8") as f:
            json.dump(filter_data, f, indent=2)
            
        print(f"Successfully analyzed local HTML! Panels: {len(filter_data['panels'])}, Inputs: {len(filter_data['inputs'])}, OptionLists: {len(filter_data['optionLists'])}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
