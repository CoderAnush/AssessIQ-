import re

def main():
    with open("data/raw/page_source.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    terms = ["Graduate", "Director", "Professional", "Manager", "Executive", "Senior", "Junior", "1,3,4,5,6,7,8,9"]
    for term in terms:
        count = len(re.findall(re.escape(term), html, re.IGNORECASE))
        print(f"Term '{term}': found {count} times")
        
    # Let's print snippets around 'Graduate' or 'job_level' or 'joblevel' (case-insensitive)
    for term in ["job_level", "joblevel", "joblevels", "job-level", "job level"]:
        matches = list(re.finditer(re.escape(term), html, re.IGNORECASE))
        print(f"Term '{term}': found {len(matches)} matches")
        for m in matches[:5]:
            start = max(0, m.start() - 100)
            end = min(len(html), m.end() + 200)
            print(f"  Snippet: {html[start:end].replace(chr(10), ' ')}")

if __name__ == "__main__":
    main()
