import json

def main():
    try:
        with open("data/raw/filter_structure.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"Total matches found: {len(data)}")
        for i, match in enumerate(data):
            print(f"\n--- MATCH {i}: {match.get('tagName')} (class: {match.get('className')}, id: {match.get('id')}) ---")
            html = match.get("outerHTML")
            # print up to 2000 chars of HTML
            print(html[:2000])
            print("..." if len(html) > 2000 else "")
            
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    main()
