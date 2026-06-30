import re

def main():
    with open("data/raw/site.js", "r", encoding="utf-8") as f:
        js = f.read()
        
    # Search for occurrences of column filtering, DataTable or table search
    keywords = ["column", "columns", "search", "filter", "data", "row", "targets", "visible"]
    for kw in keywords:
        matches = list(re.finditer(re.escape(kw), js, re.IGNORECASE))
        print(f"Keyword '{kw}': found {len(matches)} matches")
        
    # Let's print sections of JS related to column filtering
    # Specifically search for column search or filters matching e.g. columns(3) or columns(4)
    matches = list(re.finditer(r'column\(\d+\)', js))
    print(f"\nFound {len(matches)} matches for column(index) calls:")
    for m in matches:
        start = max(0, m.start() - 100)
        end = min(len(js), m.end() + 200)
        print(f"  Snippet: {js[start:end].replace(chr(10), ' ')}")

if __name__ == "__main__":
    main()
