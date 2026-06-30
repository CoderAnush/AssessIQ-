import re
import json
from pathlib import Path

# Load language mappings
def load_language_map():
    language_map = {}
    try:
        with open("data/raw/filter_mappings.json", "r", encoding="utf-8") as f:
            filter_mappings = json.load(f)
        language_map = filter_mappings.get("languages", {})
    except Exception:
        pass
    
    # Ensure lowercase keys
    language_map = {k.lower(): v for k, v in language_map.items()}
    
    # Default language mappings fallback
    default_languages = {
        "ar-sa": "Arabic", "zh-chs": "Chinese (Simplified)", "zh-cht": "Chinese (Traditional)",
        "cs-cz": "Czech", "da-dk": "Danish", "nl-nl": "Dutch", "nl-be": "Dutch (Flemish)",
        "en-gb": "English (International)", "en-us": "English (USA)", "fi-fi": "Finnish",
        "fr-fr": "French", "fr-be": "French (Belgium)", "fr-ca": "French (Canada)",
        "de-de": "German", "el-gr": "Greek", "hu-hu": "Hungarian", "is-is": "Icelandic",
        "id-id": "Indonesian", "it-it": "Italian", "ja-jp": "Japanese", "ko-kr": "Korean",
        "nn-no": "Norwegian", "pt-pt": "Portuguese", "pt-br": "Portuguese (Brasil)",
        "ro-ro": "Romanian", "ru-ru": "Russian", "sk-sk": "Slovakian", "es-es": "Spanish",
        "es-mx": "Spanish (Latin America)", "sv-se": "Swedish", "th-th": "Thai", "tr-tr": "Turkish"
    }
    
    for k, v in default_languages.items():
        if k not in language_map:
            language_map[k] = v
            
    return language_map

def parse_raw_row(row, idx, language_map):
    icon_html, name_html, description, locales_str, job_levels_str, industries_str, propositions_str, product_type_str, training_levels_str = row
    
    # 1. Strip name_html to get name
    name = re.sub(r'<[^>]+>', '', name_html).strip()
    
    # 2. Generate slug/id
    id_name = name.lower()
    id_name = id_name.replace("c#", "c-sharp").replace("c++", "c-plus-plus")
    slug = re.sub(r'[^a-z0-9]+', '-', id_name).strip('-')
    
    # 3. Construct URL
    url = f"https://www.shl.com/solutions/products/product-catalog/view/{slug}"
    
    # 4. Clean description
    description = description.strip() if description else ""
    if not description:
        description = f"SHL assessment measuring skills in {name}."
        
    # 5. Parse languages
    languages = []
    if locales_str and locales_str != "NULL":
        locales = [loc.strip().lower() for loc in locales_str.split(",") if loc.strip()]
        for loc in locales:
            lang_name = language_map.get(loc)
            if lang_name and lang_name not in languages:
                languages.append(lang_name)
    if not languages:
        languages = ["English (USA)"] # Default fallback
        
    # 6. Parse job levels
    # Job levels in raw data: e.g. "1,3,4,5,6,7,8,9"
    # We map them to: 'junior', 'mid', 'senior', 'executive'
    seniority_fit = set()
    if job_levels_str and job_levels_str != "NULL":
        levels = [l.strip() for l in job_levels_str.split(",") if l.strip()]
        for l in levels:
            if l == "4": # Graduate/Entry
                seniority_fit.add("junior")
            elif l == "5": # Professional
                seniority_fit.update(["junior", "mid", "senior"])
            elif l == "3": # Manager
                seniority_fit.update(["mid", "senior"])
            elif l in ["1", "6", "7", "8", "9"]: # Executive/Senior Management/Director
                seniority_fit.update(["senior", "executive"])
    if not seniority_fit:
        seniority_fit = {"junior", "mid", "senior", "executive"} # Default all
    seniority_fit = sorted(list(seniority_fit))
    
    # 7. Infer test_type (P, A, or K)
    test_type = 'K' # Default to knowledge/skills
    desc_lower = description.lower()
    name_lower = name.lower()
    
    # Check for personality indicators
    if any(x in name_lower or x in desc_lower for x in ["personality", "trait", "opq", "behavioral", "style", "16pf", "motivation", "preference"]):
        test_type = 'P'
    # Check for cognitive/ability indicators
    elif any(x in name_lower or x in desc_lower for x in ["reasoning", "cognitive", "ability", "aptitude", "numerical", "verbal", "logic", "spatial", "critical thinking"]):
        test_type = 'A'
        
    # 8. Infer duration
    duration = 30 # Default
    dur_match = re.search(r'(\d+)\s*-?\s*minute', desc_lower)
    if dur_match:
        duration = int(dur_match.group(1))
        
    # 9. Inferred skills
    skills = []
    # Add key terms from description/name as skills
    if test_type == 'K':
        clean_skill_name = name.replace("Fundamentals", "").replace("Test", "").replace("Short Form", "").strip()
        skills.append(clean_skill_name)
    else:
        # personality or ability skills
        if test_type == 'P':
            skills.extend(["Behavioral Style", "Workplace Behavior"])
        else:
            skills.extend(["Cognitive Ability", "Problem Solving"])
            
    return {
        "id": slug,
        "name": name,
        "url": url,
        "description": description,
        "skills": skills,
        "duration_minutes": duration,
        "test_type": test_type,
        "seniority_fit": seniority_fit,
        "languages": languages,
        "adaptive": "adaptive" in desc_lower or "computer adaptive" in desc_lower,
        "remote_testing": True
    }

def main():
    print("Normalizing scraped catalog...")
    
    live_path = Path("data/raw/raw_scraped_catalog.json")
    if not live_path.exists():
        print(f"Error: Scraped catalog not found at {live_path}")
        return
        
    with open(live_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    raw_assessments = data.get("assessments", [])
    print(f"Found {len(raw_assessments)} raw assessments.")
    
    language_map = load_language_map()
    
    normalized_assessments = []
    for idx, row in enumerate(raw_assessments):
        try:
            parsed = parse_raw_row(row, idx, language_map)
            normalized_assessments.append(parsed)
        except Exception as e:
            print(f"Error parsing row {idx}: {e}")
            
    output_path = Path("data/raw/catalog.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_assessments, f, indent=2)
        
    print(f"Normalized {len(normalized_assessments)} assessments and wrote to {output_path}")

if __name__ == "__main__":
    main()
