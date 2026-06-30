import re
import json

def main():
    try:
        with open("data/raw/page_source.html", "r", encoding="utf-8") as f:
            html = f.read()
            
        # Find comments
        comments = re.findall(r'<!--.*?-->', html, re.DOTALL)
        
        # Find the comment that contains the filter groups
        filter_comment = None
        for c in comments:
            if "fsgroup-ProductTypes" in c:
                filter_comment = c
                break
                
        if not filter_comment:
            print("Could not find the comment containing filter groups.")
            return
            
        print("Found filter comment block! Parsing...")
        
        # Mappings dictionaries
        mappings = {
            "product_types": {},
            "industries": {},
            "job_levels": {},
            "propositions": {},
            "languages": {}
        }
        
        # Parse links using regex
        # Structure: <a aria-label="Label" class="shl-fs-item" href="...url..." role="link">Label</a>
        # URL has query params: producttypes=X, industries=X, joblevels=X, propositions=X, etc.
        # Let's extract all links in the comment block
        links = re.findall(r'<a\s+aria-label="([^"]+)"\s+class="shl-fs-item"\s+href="([^"]+)"\s+role="link">', filter_comment)
        print(f"Found {len(links)} links in the filter comment.")
        
        for label, url in links:
            url_decoded = url.replace("&amp;", "&")
            
            # Match product types
            pt_match = re.search(r'producttypes=(\d+)', url_decoded)
            if pt_match:
                mappings["product_types"][pt_match.group(1)] = label
                
            # Match industries
            ind_match = re.search(r'industries=(\d+)', url_decoded)
            if ind_match:
                mappings["industries"][ind_match.group(1)] = label
                
            # Match job levels
            jl_match = re.search(r'joblevels=(\d+)', url_decoded)
            if jl_match:
                mappings["job_levels"][jl_match.group(1)] = label
                
            # Match propositions
            prop_match = re.search(r'propositions=(\d+)', url_decoded)
            if prop_match:
                mappings["propositions"][prop_match.group(1)] = label
                
            # Match languages
            lang_match = re.search(r'languages=([^&]+)', url_decoded)
            if lang_match:
                mappings["languages"][lang_match.group(1)] = label
                
        # Also check for disabled elements (which are not links, but plain text)
        # E.g. <li role="listitem" class="shl-disabled">\n\t\t\t\t\t\tPJM\n\t\t\t\t\t\t<span>(0)</span>\n\t\t\t\t\t</li>
        # These don't have IDs in this comment, but the links have IDs and labels.
        
        print("\nExtracted Mappings:")
        print("Product Types:", mappings["product_types"])
        print("Industries:", mappings["industries"])
        print("Job Levels:", mappings["job_levels"])
        print("Propositions:", mappings["propositions"])
        print("Languages Count:", len(mappings["languages"]))
        
        # Save to file
        with open("data/raw/filter_mappings.json", "w", encoding="utf-8") as f:
            json.dump(mappings, f, indent=2)
            
        print("\nSaved mappings to data/raw/filter_mappings.json")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
