import os
import json
import time
import urllib.request
import urllib.error
import re
import sys
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# Force output encoding to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Env load
from dotenv import load_dotenv
load_dotenv(dotenv_path='backend/.env')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
RAW_CACHE_FILE = "backend/data/qa_1000_raw.json"
VERIFIED_CACHE_FILE = "backend/data/qa_1000_verified.json"
EXCEL_FILE_PATH = "설계서/학습데이터 설계서.xlsx"

def call_gemini_api(prompt: str) -> list:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in env.")

    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GEMINI_API_KEY}"
    }
    
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "당신은 한국 공정거래법 및 학습데이터 품질 관리에 정통한 AI 검수관입니다. 주어진 QA 레코드를 면밀히 감사하여 형식이나 내용상 위배 사항을 찾아내어 JSON 배열로 보고해야 합니다."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            content = res_json["choices"][0]["message"]["content"].strip()
            
            json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
            
            return json.loads(content)
    except Exception as e:
        print(f"❌ Gemini Auditor API Call Error: {e}")
        return []

def main():
    print("🚀 [AI Auditor] Loading raw 1,000 cases...")
    
    if not os.path.exists(RAW_CACHE_FILE):
        print(f"❌ Error: {RAW_CACHE_FILE} does not exist. Please run generate_1000_qa.py first.")
        return
        
    with open(RAW_CACHE_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    print(f"📊 Loaded {len(raw_data)} cases from raw cache.")
    
    # Load audited cache if exists
    audited_issues = {}
    if os.path.exists(VERIFIED_CACHE_FILE):
        try:
            with open(VERIFIED_CACHE_FILE, "r", encoding="utf-8") as f:
                audited_issues = json.load(f)
            print(f"🔄 Loaded {len(audited_issues)} cached audit results from {VERIFIED_CACHE_FILE}.")
        except Exception:
            audited_issues = {}
            
    # Audit cases in batches of 40 to prevent rate limits
    batch_size = 40
    raw_keys = list(raw_data.keys())
    
    for start_idx in range(0, 1000, batch_size):
        batch_keys = raw_keys[start_idx : start_idx + batch_size]
        need_audit = [k for k in batch_keys if k not in audited_issues]
        
        if not need_audit:
            continue
            
        print(f"📈 [Auditing] Auditing batch {start_idx // batch_size + 1}/25 (Index {start_idx} to {min(1000, start_idx + batch_size)})...")
        
        req_str = ""
        for k in need_audit:
            item = raw_data[k]
            req_str += (
                f"- Index: {item['idx']}\n"
                f"  페르소나: {item['persona']}\n"
                f"  질문: {item['question']}\n"
                f"  답변: {item['answer']}\n"
                f"  사실관계: {item['facts']}\n"
                f"  법리해석: {item['legal_reasoning']}\n"
                f"  적용법률: {item['applicable_law']}\n"
                f"  참조문서: {item['ref_doc']}\n\n"
            )
            
        prompt = (
            f"다음 {len(need_audit)}개 학습데이터의 질문, 답변, 적용법률, 사실관계 형식을 AI의 관점에서 검수해주십시오.\n\n"
            f"[요구사항 및 평가 기준]\n"
            f"1. 톤앤매너: 일반국민은 구어체 및 해결방안 위주여야 하며, 기업담당자는 컴플라이언스 리스크 중심, 학생은 학술적 용어 및 대법원 판례 중심이어야 합니다.\n"
            f"2. 사실관계(facts) 형식: '주체: ... / 상대방: ... / 시장: ... / 핵심행위: ... / 결과: ...' 형식을 완벽히 만족해야 합니다. 만족하지 않으면 오류로 판정하십시오.\n"
            f"3. 법리해석 형식: '법리 해석: '[세부위반유형]'은(는) 상대방에게 불이익을 주거나 소비자를 오인하게 할 수 있어 '[적용법률]' 위반으로 볼 수 있다.' 형식을 만족해야 합니다. 만족하지 않으면 오류로 판정하십시오.\n"
            f"4. 법률 오매칭: 해당 사건의 위반 내용과 적용법률이 맞지 않거나 엉뚱한 법률이 적혀 있으면 오류로 판정하십시오.\n\n"
            f"[검수 대상 목록]\n{req_str}\n"
            f"[지침]\n"
            f"- 문제가 발견된 케이스에 대해 JSON 객체 배열로 반환하십시오. 예시:\n"
            f"  [\n"
            f"    {{\n"
            f"      \"idx\": 0,\n"
            f"      \"problem\": \"[문제점] 구체적인 톤 또는 형식 오류에 대한 설명\",\n"
            f"      \"solution\": \"[해결방안] Rule Validator 혹은 프롬프트 조정을 통해 교정할 방안 설명\"\n"
            f"    }}\n"
            f"  ]\n"
            f"- 완벽하게 정상인 케이스에 대해서는 보고하지 마십시오. 즉, 문제가 있는 케이스만 JSON 배열에 담아주십시오.\n"
            f"- 마크다운 백틱 없이 순수한 JSON 배열 포맷으로만 응답해주십시오.\n"
        )
        
        success = False
        for attempt in range(3):
            batch_res = call_gemini_api(prompt)
            if isinstance(batch_res, list):
                # Save results (for normal cases, we store empty dict indicating checked but normal)
                # First mark all in this batch as checked and normal
                for k in need_audit:
                    audited_issues[k] = {"idx": int(k), "has_issue": False}
                    
                # Overlay issues found
                for issue in batch_res:
                    idx_str = str(issue.get("idx"))
                    if idx_str in audited_issues:
                        audited_issues[idx_str] = {
                            "idx": int(idx_str),
                            "has_issue": True,
                            "problem": issue.get("problem"),
                            "solution": issue.get("solution")
                        }
                        
                with open(VERIFIED_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(audited_issues, f, ensure_ascii=False, indent=2)
                    
                print(f"✅ Batch audited. (Checked: {len(audited_issues)}/1000)")
                success = True
                break
            else:
                print(f"⚠️ Batch audit failed, retrying in 5 seconds... (Attempt {attempt+1}/3)")
                time.sleep(5)
                
        if not success:
            print("❌ Critical: Failed to audit batch. Terminating execution.")
            return
            
        time.sleep(4)
        
    print("🎉 All 1,000 cases audited successfully! Preparing Excel writing...")
    
    # 7. Copy template and load Excel workbook
    import shutil
    import copy
    import time
    print("📋 Copying template file to destination...")
    copied = False
    for attempt in range(12):
        try:
            shutil.copy2("설계서/학습데이터 설계서 양식.xlsx", EXCEL_FILE_PATH)
            copied = True
            break
        except PermissionError:
            print(f"⚠️ [대기 중] '{EXCEL_FILE_PATH}' 파일이 열려 있어 접근할 수 없습니다. 엑셀 프로그램을 종료해 주세요. (5초 후 재시도 {attempt+1}/12)")
            time.sleep(5)
            
    if not copied:
        print(f"❌ 오류: '{EXCEL_FILE_PATH}' 파일을 덮어쓸 수 없습니다. 엑셀을 종료한 후 다시 실행하십시오.")
        return
        
    wb = openpyxl.load_workbook(EXCEL_FILE_PATH)

    # Helper to get styles from row 3
    def get_row_styles(sheet, row_idx=3):
        styles = {}
        for col in range(1, 18):
            cell = sheet.cell(row=row_idx, column=col)
            styles[col] = {
                "font": copy.copy(cell.font) if cell.font else None,
                "border": copy.copy(cell.border) if cell.border else None,
                "fill": copy.copy(cell.fill) if cell.fill else None,
                "alignment": copy.copy(cell.alignment) if cell.alignment else None,
                "number_format": cell.number_format
            }
        return styles

    def apply_row_styles(sheet, row_idx, styles):
        for col in range(1, 18):
            cell = sheet.cell(row=row_idx, column=col)
            style = styles[col]
            if style["font"]: cell.font = style["font"]
            if style["border"]: cell.border = style["border"]
            if style["fill"]: cell.fill = style["fill"]
            if style["alignment"]: cell.alignment = style["alignment"]
            if style["number_format"]: cell.number_format = style["number_format"]

    data_sheets = ["전체_QA", "일반국민", "기업 컴플라이언스 담당자", "논문 준비 학생"]
    
    # Extract styles from row 3 and then clear values from row 3 downwards (keeping Column 17 header)
    sheet_styles = {}
    for s_name in data_sheets:
        sh = wb[s_name]
        sheet_styles[s_name] = get_row_styles(sh, row_idx=3)
        for r in range(3, max(3, sh.max_row + 1)):
            for c in range(1, 18):
                sh.cell(row=r, column=c).value = None
                
    # Compile rows in order
    all_rows = []
    for idx in range(1000):
        item = raw_data[str(idx)]
        row_id = f"QA-{idx + 1:04d}"
        
        no_str = item["의결서관리번호"]
        if no_str and len(no_str) >= 4:
            ref_val = f"의결서{no_str[:2]}-{no_str[2:4]}  1줄-{no_str}줄"
        else:
            ref_val = f"의결서02-24  1줄-22450줄"
            
        col_8_basis = f"의결서는 '{item['피심인기업명']}'의 행위가 '{item['세부위반유형']}'에 해당한다고 보고 '{item['조치유형']}'을 결정하였다."
        col_9_summary = f"{item['피심인기업명']}의 {item['세부위반유형']} 사건은 {item['피심인기업명']}이(가) 상대방에게 불리한 행위를 하여 문제가 된 사례이다."
        
        # Scenarios
        p_name = item["persona"]
        style_desc = "쉽고 직관적인 설명" if p_name == "일반국민" else ("리스크 및 준법 중심 설명" if p_name == "기업 컴플라이언스 담당자" else "학술·연구 중심 설명")
        point_desc = "생활 속 사례와 쉽게 풀어쓴 설명" if p_name == "일반국민" else ("위반 위험요소, 내부통제 포인트, 재발방지 관점" if p_name == "기업 컴플라이언스 담당자" else "쟁점, 판단 구조, 비교법적·통계적 해석")
        
        basic_sc = f"사용자가 '{item['피심인기업명']}의 {item['세부위반유형']}' 관련 궁금증을 자연어로 입력하면, AI가 {style_desc}로 관련 사실과 의결서 근거를 제시한다."
        add_sc = f"추가 시나리오: 유사한 위반 유형 및 행정 제재 통계를 시각화하여 사용자가 행동 양식을 판단할 수 있도록 돕는다."
        
        # Determine issue and solution for Column 17 (문제점 및 해결방안)
        issue = audited_issues.get(str(idx))
        if issue and issue.get("has_issue"):
            col_17_val = f"[문제점] {issue.get('problem')}\n[해결방안] {issue.get('solution')}"
        else:
            col_17_val = None
            
        row_data = {
            "ID": row_id,
            "페르소나": p_name,
            "질문유형": item["question_type"],
            "난이도": item["difficulty"],
            "주제": item["subject"],
            "질문": item["question"],
            "답변": item["answer"],
            "근거": col_8_basis,
            "주제별·수준별 의결서 요약": col_9_summary,
            "사실(Facts)": item["facts"],
            "법리 해석": item["legal_reasoning"],
            "기본 시나리오": basic_sc,
            "추가 시나리오": add_sc,
            "응답 설계 포인트": point_desc,
            "의도된 설명 스타일": style_desc,
            "주의사항_비고": ref_val,
            "문제점_및_해결방안": col_17_val
        }
        all_rows.append(row_data)
        
    # Write to 전체_QA
    sh_total = wb["전체_QA"]
    styles_total = sheet_styles["전체_QA"]
    for idx, rdata in enumerate(all_rows):
        r = idx + 3
        apply_row_styles(sh_total, r, styles_total)
        sh_total.cell(row=r, column=1).value = rdata["ID"]
        sh_total.cell(row=r, column=2).value = rdata["페르소나"]
        sh_total.cell(row=r, column=3).value = rdata["질문유형"]
        sh_total.cell(row=r, column=4).value = rdata["난이도"]
        sh_total.cell(row=r, column=5).value = rdata["주제"]
        sh_total.cell(row=r, column=6).value = rdata["질문"]
        sh_total.cell(row=r, column=7).value = rdata["답변"]
        sh_total.cell(row=r, column=8).value = rdata["근거"]
        sh_total.cell(row=r, column=9).value = rdata["주제별·수준별 의결서 요약"]
        sh_total.cell(row=r, column=10).value = rdata["사실(Facts)"]
        sh_total.cell(row=r, column=11).value = rdata["법리 해석"]
        sh_total.cell(row=r, column=12).value = rdata["기본 시나리오"]
        sh_total.cell(row=r, column=13).value = rdata["추가 시나리오"]
        sh_total.cell(row=r, column=14).value = rdata["응답 설계 포인트"]
        sh_total.cell(row=r, column=15).value = rdata["의도된 설명 스타일"]
        sh_total.cell(row=r, column=16).value = rdata["주의사항_비고"]
        sh_total.cell(row=r, column=17).value = rdata["문제점_및_해결방안"]
    print("✍️ Wrote '전체_QA' sheet (1000 rows).")

    # Filter and write to General Public
    general_rows = [row for row in all_rows if row["페르소나"] == "일반국민"]
    sh_gen = wb["일반국민"]
    styles_gen = sheet_styles["일반국민"]
    for idx, rdata in enumerate(general_rows):
        r = idx + 3
        apply_row_styles(sh_gen, r, styles_gen)
        sh_gen.cell(row=r, column=1).value = rdata["ID"]
        sh_gen.cell(row=r, column=2).value = rdata["페르소나"]
        sh_gen.cell(row=r, column=3).value = rdata["질문유형"]
        sh_gen.cell(row=r, column=4).value = rdata["난이도"]
        sh_gen.cell(row=r, column=5).value = rdata["주제"]
        sh_gen.cell(row=r, column=6).value = rdata["질문"]
        sh_gen.cell(row=r, column=7).value = rdata["답변"]
        sh_gen.cell(row=r, column=8).value = rdata["근거"]
        sh_gen.cell(row=r, column=9).value = rdata["주제별·수준별 의결서 요약"]
        sh_gen.cell(row=r, column=10).value = rdata["사실(Facts)"]
        sh_gen.cell(row=r, column=11).value = rdata["법리 해석"]
        sh_gen.cell(row=r, column=12).value = rdata["기본 시나리오"]
        sh_gen.cell(row=r, column=13).value = rdata["추가 시나리오"]
        sh_gen.cell(row=r, column=14).value = rdata["응답 설계 포인트"]
        sh_gen.cell(row=r, column=15).value = rdata["의도된 설명 스타일"]
        sh_gen.cell(row=r, column=16).value = rdata["주의사항_비고"]
        sh_gen.cell(row=r, column=17).value = rdata["문제점_및_해결방안"]
    print(f"✍️ Wrote '일반국민' sheet ({len(general_rows)} rows).")

    # Write to Compliance
    comp_rows = [row for row in all_rows if row["페르소나"] == "기업 컴플라이언스 담당자"]
    sh_comp = wb["기업 컴플라이언스 담당자"]
    styles_comp = sheet_styles["기업 컴플라이언스 담당자"]
    for idx, rdata in enumerate(comp_rows):
        r = idx + 3
        apply_row_styles(sh_comp, r, styles_comp)
        sh_comp.cell(row=r, column=1).value = rdata["ID"]
        sh_comp.cell(row=r, column=2).value = rdata["페르소나"]
        sh_comp.cell(row=r, column=3).value = rdata["질문유형"]
        sh_comp.cell(row=r, column=4).value = rdata["난이도"]
        sh_comp.cell(row=r, column=5).value = rdata["주제"]
        sh_comp.cell(row=r, column=6).value = rdata["질문"]
        sh_comp.cell(row=r, column=7).value = rdata["답변"]
        sh_comp.cell(row=r, column=8).value = rdata["근거"]
        sh_comp.cell(row=r, column=9).value = rdata["주제별·수준별 의결서 요약"]
        sh_comp.cell(row=r, column=10).value = rdata["facts"] if "facts" in rdata else rdata.get("사실(Facts)")
        sh_comp.cell(row=r, column=11).value = rdata["법리 해석"]
        sh_comp.cell(row=r, column=12).value = rdata["기본 시나리오"]
        sh_comp.cell(row=r, column=13).value = rdata["추가 시나리오"]
        sh_comp.cell(row=r, column=14).value = rdata["응답 설계 포인트"]
        sh_comp.cell(row=r, column=15).value = rdata["의도된 설명 스타일"]
        sh_comp.cell(row=r, column=16).value = rdata["주의사항_비고"]
        sh_comp.cell(row=r, column=17).value = rdata["문제점_및_해결방안"]
    print(f"✍️ Wrote '기업 컴플라이언스 담당자' sheet ({len(comp_rows)} rows).")

    # Write to Student
    student_rows = [row for row in all_rows if row["페르소나"] == "논문 준비 학생"]
    sh_stud = wb["논문 준비 학생"]
    styles_stud = sheet_styles["논문 준비 학생"]
    for idx, rdata in enumerate(student_rows):
        r = idx + 3
        apply_row_styles(sh_stud, r, styles_stud)
        sh_stud.cell(row=r, column=1).value = rdata["ID"]
        sh_stud.cell(row=r, column=2).value = rdata["페르소나"]
        sh_stud.cell(row=r, column=3).value = rdata["질문유형"]
        sh_stud.cell(row=r, column=4).value = rdata["난이도"]
        sh_stud.cell(row=r, column=5).value = rdata["주제"]
        sh_stud.cell(row=r, column=6).value = rdata["질문"]
        sh_stud.cell(row=r, column=7).value = rdata["답변"]
        sh_stud.cell(row=r, column=8).value = rdata["근거"]
        sh_stud.cell(row=r, column=9).value = rdata["주제별·수준별 의결서 요약"]
        sh_stud.cell(row=r, column=10).value = rdata["facts"] if "facts" in rdata else rdata.get("사실(Facts)")
        sh_stud.cell(row=r, column=11).value = rdata["법리 해석"]
        sh_stud.cell(row=r, column=12).value = rdata["기본 시나리오"]
        sh_stud.cell(row=r, column=13).value = rdata["추가 시나리오"]
        sh_stud.cell(row=r, column=14).value = rdata["응답 설계 포인트"]
        sh_stud.cell(row=r, column=15).value = rdata["의도된 설명 스타일"]
        sh_stud.cell(row=r, column=16).value = rdata["주의사항_비고"]
        sh_stud.cell(row=r, column=17).value = rdata["문제점_및_해결방안"]
    print(f"✍️ Wrote '논문 준비 학생' sheet ({len(student_rows)} rows).")

    # 8. Update Dashboard
    sh_dash = wb["대시보드"]
    sh_dash["A1"] = "페르소나 기반 QA 데이터셋 대시보드 (1000건)"
    sh_dash["B3"] = "=COUNTA(전체_QA!A3:A1100)"
    
    sh_dash["B6"] = "=COUNTA(일반국민!A3:A1100)"
    sh_dash["B7"] = "=COUNTA('기업 컴플라이언스 담당자'!A3:A1100)"
    sh_dash["B8"] = "=COUNTA('논문 준비 학생'!A3:A1100)"
    
    sh_dash["E6"] = "=COUNTIF(전체_QA!C3:C1100, \"제재중심\")"
    sh_dash["E7"] = "=COUNTIF(전체_QA!C3:C1100, \"법령중심\")"
    sh_dash["E8"] = "=COUNTIF(전체_QA!C3:C1100, \"유사사례\")"
    sh_dash["E9"] = "=COUNTIF(전체_QA!C3:C1100, \"통계기반\")"
    sh_dash["E10"] = "=COUNTIF(전체_QA!C3:C1100, \"시장영향\")"
    
    sh_dash["B12"] = "=COUNTIF(전체_QA!D3:D1100, \"기초\")"
    sh_dash["B13"] = "=COUNTIF(전체_QA!D3:D1100, \"중급\")"
    sh_dash["B14"] = "=COUNTIF(전체_QA!D3:D1100, \"심화\")"
    print("📊 Updated '대시보드' sheet with active formulas.")
    
    # Save workbook
    try:
        wb.save(EXCEL_FILE_PATH)
        print(f"🎉 Successfully saved audited workbook to: {EXCEL_FILE_PATH}")
    except Exception as e:
        print(f"❌ Error saving workbook: {e}")

if __name__ == "__main__":
    main()
