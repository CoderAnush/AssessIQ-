import re

def main():
    with open("data/raw/page_source.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    matches = list(re.finditer("fsgroup-JobLevels", html, re.IGNORECASE))
    print(f"Found {len(matches)} matches for fsgroup-JobLevels:")
    for m in matches:
        start = max(0, m.start() - 200)
        end = min(len(html), m.end() + 2000)
        print(f"\n--- Match at index {m.start()} ---")
        print(html[start:end])

if __name__ == "__main__":
    main()
