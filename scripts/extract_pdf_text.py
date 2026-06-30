import pdfplumber

def main():
    try:
        with pdfplumber.open("SHL_AI_Intern_Assignment-1.pdf") as pdf:
            text = ""
            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                text += f"\n--- PAGE {i} ---\n"
                text += page_text if page_text else "[Empty Page]"
                text += "\n"
                
        with open("data/raw/assignment_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
            
        print("Successfully extracted PDF text to data/raw/assignment_text.txt")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
