import re

def main():
    try:
        with open("data/raw/page_source.html", "r", encoding="utf-8") as f:
            html = f.read()
            
        comments = re.findall(r'<!--.*?-->', html, re.DOTALL)
        
        with open("data/raw/comments_dump.txt", "w", encoding="utf-8") as out:
            out.write(f"Found {len(comments)} comments:\n")
            for i, c in enumerate(comments):
                out.write(f"\n=========================================\n")
                out.write(f"COMMENT {i} (length: {len(c)})\n")
                out.write(f"=========================================\n")
                out.write(c)
                out.write("\n")
                
        print("Done! Comments written to data/raw/comments_dump.txt")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
