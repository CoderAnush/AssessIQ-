import re

def search_file(path, keywords):
    print(f"\nSearching file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        for kw in keywords:
            matches = list(re.finditer(re.escape(kw), content, re.IGNORECASE))
            print(f"  Keyword '{kw}': found {len(matches)} matches")
            for m in matches[:5]:
                start = max(0, m.start() - 150)
                end = min(len(content), m.end() + 250)
                snippet = content[start:end].replace("\n", " ").replace("\r", "")
                print(f"    Snippet: {snippet}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    keywords = ["job_level", "joblevel", "joblevels", "jobLevelName", "job-level", "job level", "Graduate", "Director", "Executive", "Professional"]
    search_file("data/raw/site.js", keywords)
    search_file("data/raw/js_lib.js", keywords)

if __name__ == "__main__":
    main()
