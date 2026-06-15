import fitz
import os
import glob

pdf_files = glob.glob("forms/*.pdf")
templates = {}

for pdf_file in pdf_files:
    try:
        doc = fitz.open(pdf_file)
        # Extract page 1 (the form) and maybe page 6 (the example) to give LLM good context
        text = "=== [양식 본문] ===\n" + doc[0].get_text()
        
        # If there's an example on the last page, append it
        if len(doc) >= 6:
            text += "\n=== [작성 예시] ===\n" + doc[-1].get_text()
            
        name = os.path.basename(pdf_file).replace(".pdf", "")
        templates[name] = text
    except Exception as e:
        print(f"Error reading {pdf_file}: {e}")

os.makedirs("modules", exist_ok=True)
with open("modules/templates.py", "w", encoding="utf-8") as f:
    f.write('"""\n이 파일은 템플릿 PDF들로부터 자동 생성되었습니다.\n"""\n\n')
    f.write("FORM_TEMPLATES = {\n")
    for name, text in templates.items():
        f.write(f'    "{name}": """{text}""",\n')
    f.write("}\n")

print(f"Successfully extracted {len(templates)} templates to modules/templates.py")
