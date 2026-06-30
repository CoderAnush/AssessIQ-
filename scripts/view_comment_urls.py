import re

def main():
    with open("data/raw/page_source.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    comments = re.findall(r'<!--.*?-->', html, re.DOTALL)
    filter_comment = next(c for c in comments if "fsgroup-ProductTypes" in c)
    
    links = re.findall(r'<a\s+aria-label="([^"]+)"\s+class="shl-fs-item"\s+href="([^"]+)"\s+role="link">', filter_comment)
    
    for label, url in links:
        print(f"Label: {label} | URL: {url}")

if __name__ == "__main__":
    main()
