import re

def main():
    with open("data/raw/page_source.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    # Extract src attributes of script tags
    srcs = re.findall(r'<script\s+[^>]*src="([^"]+)"', html)
    print("Script URLs:")
    for src in srcs:
        print(f"  {src}")
        
    # Extract inline scripts
    inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"\nInline scripts count: {len(inline_scripts)}")
    for i, script in enumerate(inline_scripts):
        if any(term in script for term in ["DataTable", "Table", "myTable", "job", "level", "mapping", "propositions"]):
            print(f"\n--- Script {i} (length: {len(script)}) ---")
            print(script[:1500])
            print("..." if len(script) > 1500 else "")

if __name__ == "__main__":
    main()
