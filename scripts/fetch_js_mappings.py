import requests
import re
import json

def search_js(url):
    print(f"Fetching JS: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        text = response.text
        print(f"Length: {len(text)}")
        
        # Search for job levels, propositions, or other filter mappings
        for keyword in ["job_level", "joblevel", "propositions", "industries", "Graduate", "Manager", "Executive", "Director"]:
            count = len(re.findall(re.escape(keyword), text, re.IGNORECASE))
            print(f"  Keyword '{keyword}': found {count} times")
            
            # Print a few matches
            if count > 0:
                matches = list(re.finditer(re.escape(keyword), text, re.IGNORECASE))
                for m in matches[:3]:
                    start = max(0, m.start() - 100)
                    end = min(len(text), m.end() + 200)
                    print(f"    Match: {text[start:end].replace(chr(10), ' ')}")
    except Exception as e:
        print(f"Error fetching JS: {e}")

def main():
    base_url = "https://online.shl.com"
    search_js(base_url + "/scripts/js?v=CHMxBjcG4f5EwaN_Nm9iCojyYaGhZzh_3XLZrZqkcyE1")
    search_js(base_url + "/scripts/sitejs?v=zSuY6hFq_0PoJ0TWAR6pTaQhPuOqSxb0c8OtQ3rdgVQ1")

if __name__ == "__main__":
    main()
