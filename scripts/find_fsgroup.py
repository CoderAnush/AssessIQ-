import re

def main():
    try:
        with open("data/raw/page_source.html", "r", encoding="utf-8") as f:
            html = f.read()
            
        print(f"Total HTML length: {len(html)}")
        
        # Search for occurrences of fsgroup-
        matches = re.findall(r'fsgroup-[a-zA-Z0-9]+', html)
        print(f"fsgroup- occurrences: {set(matches)}")
        
        # Look for commented HTML starting with fsgroup-
        comments = re.findall(r'<!--.*?-->', html, re.DOTALL)
        print(f"Total comments found: {len(comments)}")
        
        # Let's print any comments that contain 'fsgroup-' or 'Job Level' or 'Category'
        filter_comments = [c for c in comments if any(term in c for term in ['fsgroup-', 'Job Level', 'Category', 'Proposition', 'Product Type'])]
        print(f"Comments containing filter keywords: {len(filter_comments)}")
        for i, c in enumerate(filter_comments[:5]):
            print(f"\n--- Comment {i} ---")
            print(c[:1000])
            print("..." if len(c) > 1000 else "")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
