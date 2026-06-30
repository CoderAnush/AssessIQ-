import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    print("Launching Playwright in non-headless mode...")
    async with async_playwright() as p:
        # Non-headless mode is much less likely to trigger bot detection
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        url = "https://online.shl.com/gb/en-us/products"
        print(f"Navigating to {url}...")
        await page.goto(url)
        
        print("Waiting for page load and table element...")
        # Wait up to 30 seconds for DataTable to load
        try:
            await page.wait_for_selector("#myTable_wrapper", timeout=30000)
            print("DataTable loaded successfully!")
        except Exception as e:
            print("Timeout waiting for table. Please verify if human verification is required.")
            # Give user a chance to solve CAPTCHA if visible
            print("Waiting an extra 15 seconds in case of human verification...")
            await asyncio.sleep(15)
            
        print("Extracting data via page evaluation...")
        try:
            # Extract DataTable rows
            assessments = await page.evaluate("() => jQuery('#myTable').DataTable().rows().data().toArray()")
            print(f"Extracted {len(assessments)} assessments!")
            
            # Extract filters
            filters = await page.evaluate("""() => {
                const getSelectOptions = (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return {};
                    const options = {};
                    el.querySelectorAll('option').forEach(opt => {
                        if (opt.value) {
                            options[opt.value] = opt.textContent.trim();
                        }
                    });
                    return options;
                };
                
                // Job level options
                const jobLevels = getSelectOptions('select[name="job_level"]');
                // Category/Proposition options
                const propositions = getSelectOptions('select[name="proposition"]');
                // Product type options
                const productTypes = getSelectOptions('select[name="product_type"]');
                
                return { jobLevels, propositions, productTypes };
            }""")
            
            # Save raw data
            output_dir = Path("data/raw")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "raw_scraped_catalog.json"
            
            output_data = {
                "assessments": assessments,
                "filters": filters,
                "scraped_at": Path().stat().st_mtime
            }
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2)
                
            print(f"Successfully saved raw scraped catalog to {output_path}")
            
        except Exception as e:
            print(f"Error during data extraction: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
