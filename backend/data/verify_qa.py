import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "qa_dataset.json")

def verify_dataset():
    if not os.path.exists(DATA_FILE):
        print("❌ qa_dataset.json 파일이 존재하지 않습니다.")
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_count = len(data)
    print(f"==================================================")
    print(f"📊 [데이터셋 정밀 검증 보고서] 총 데이터 건수: {total_count}건")
    print(f"==================================================")

    # 1. 스키마 무결성 검증
    required_keys = {"persona", "query", "answer", "signal_color", "applicable_law"}
    schema_errors = 0
    empty_fields = 0
    
    for idx, item in enumerate(data):
        missing = required_keys - set(item.keys())
        if missing:
            print(f"  ❌ [{idx}] 필수 키 누락: {missing}")
            schema_errors += 1
        for k, v in item.items():
            if not str(v).strip():
                print(f"  ❌ [{idx}] 빈 필드 감지: {k}")
                empty_fields += 1

    print(f"✅ 스키마 누락 건수: {schema_errors}건")
    print(f"✅ 빈 데이터 감지: {empty_fields}건")

    # 2. 신호등 색상 분포 분석
    color_counts = {}
    for item in data:
        c = item.get("signal_color")
        color_counts[c] = color_counts.get(c, 0) + 1

    print("\n🟢 1) 신호등 위험도(signal_color) 분포:")
    for color, count in color_counts.items():
        ratio = (count / total_count) * 100
        print(f"   - {color:<8}: {count:>3}건 ({ratio:.1f}%)")

    # 3. 페르소나 유형 분포 분석
    persona_types = {"일반 국민": 0, "논문 준비 학생": 0, "청장년층": 0}
    for item in data:
        persona = item.get("persona", "")
        # 페르소나 내의 단어를 통해 유형 역추적
        if any(w in persona for w in ["학생", "전공생", "연구원", "대학원생"]):
            persona_types["논문 준비 학생"] += 1
        elif any(w in persona for w in ["대학생", "청년", "신입사원", "직장인", "개발자", "마케터", "간호사"]):
            persona_types["청장년층"] += 1
        else:
            persona_types["일반 국민"] += 1

    print("\n🟢 2) 페르소나 유형 분포:")
    for p_type, count in persona_types.items():
        ratio = (count / total_count) * 100
        print(f"   - {p_type:<10}: {count:>3}건 ({ratio:.1f}%)")

    # 4. 주요 위반 법률(applicable_law) 분포 분석 Top 5
    laws = {}
    for item in data:
        law = item.get("applicable_law", "").split(",")[0].split("(")[0].strip()
        laws[law] = laws.get(law, 0) + 1

    sorted_laws = sorted(laws.items(), key=lambda x: x[1], reverse=True)
    print("\n🟢 3) 주요 적용 법령 (상위 5개):")
    for law, count in sorted_laws[:5]:
        ratio = (count / total_count) * 100
        print(f"   - {law[:20]:<20}: {count:>3}건 ({ratio:.1f}%)")

    # 5. 샘플 데이터 2건 시각화
    print("\n🟢 4) 생성된 데이터 샘플:")
    for idx in [10, 800]:
        if idx < len(data):
            sample = data[idx]
            print(f"   [{idx}번째 데이터]")
            print(f"     • 페르소나: {sample['persona']}")
            print(f"     • 질문(Q) : {sample['query'][:50]}...")
            print(f"     • 답변(A) : {sample['answer'][:50]}...")
            print(f"     • 신호등  : {sample['signal_color']}")
            print(f"     • 법 령   : {sample['applicable_law']}")
            print("-" * 40)

if __name__ == "__main__":
    verify_dataset()
