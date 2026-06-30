import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://online.shl.com/gb/en-us/products')
        try:
            await page.wait_for_selector("input[type='checkbox']", timeout=15000)
        except Exception as e:
            pass
        
        # Extract inputs
        filters = await page.evaluate("""() => {
            const checkboxes = [];
            document.querySelectorAll("input[type='checkbox']").forEach(input => {
                // Find label
                let labelText = "";
                if (input.id) {
                    const label = document.querySelector(`label[for="${input.id}"]`);
                    if (label) {
                        labelText = label.textContent.trim();
                    }
                }
                if (!labelText) {
                    labelText = input.parentElement ? input.parentElement.textContent.trim() : "";
                }
                checkboxes.push({
                    name: input.name,
                    id: input.id,
                    value: input.value,
                    label: labelText
                });
            });
            
            // Also select elements
            const selects = {};
            document.querySelectorAll("select").forEach(select => {
                const name = select.name || select.id || "";
                if (name) {
                    selects[name] = {};
                    select.querySelectorAll("option").forEach(opt => {
                        if (opt.value) {
                            selects[name][opt.value] = opt.textContent.trim();
                        }
                    });
                }
            });
            
            return { checkboxes, selects };
        }""")
        
        # Save mappings first
        output_dir = Path("data/raw")
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_dir / "filter_mappings.json", "w", encoding="utf-8") as f:
            json.dump(filters, f, indent=2)
            
        print(f"Saved {len(filters['checkboxes'])} checkboxes and {len(filters['selects'])} selects to filter_mappings.json")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
