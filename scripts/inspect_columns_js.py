import re

def main():
    with open("data/raw/site.js", "r", encoding="utf-8") as f:
        js = f.read()
        
    for term in ["column", "columns", "visible", "targets", "DataTable", "myTable"]:
        matches = list(re.finditer(re.escape(term), js, re.IGNORECASE))
        print(f"\n--- {term} ({len(matches)} matches) ---")
        for m in matches[:10]:
            start = max(0, m.start() - 100)
            end = min(len(js), m.end() + 200)
            print(f"  Snippet: {js[start:end].replace(chr(10), ' ')}")

if __name__ == "__main__":
    main()
