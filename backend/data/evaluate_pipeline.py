import os
import sys
import json
import random
import argparse
from dotenv import load_dotenv

# sys.path에 backend 디렉터리 추가하여 로컬 모듈 임포트 가능하도록 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 파일 로드
load_dotenv()

DATA_FILE = os.path.join(os.path.dirname(__file__), "qa_dataset.json")

def calculate_metrics(y_true, y_pred):
    """
    Precision, Recall, F1-score 및 Accuracy를 수동으로 계산합니다.
    """
    classes = ["RED", "YELLOW", "GREEN"]
    confusion_matrix = {c: {pred: 0 for pred in classes} for c in classes}
    
    for t, p in zip(y_true, y_pred):
        if t in classes and p in classes:
            confusion_matrix[t][p] += 1
            
    accuracy = sum(confusion_matrix[c][c] for c in classes) / len(y_true) if y_true else 0
    
    report = {}
    for c in classes:
        tp = confusion_matrix[c][c]
        fp = sum(confusion_matrix[other][c] for other in classes if other != c)
        fn = sum(confusion_matrix[c][other] for other in classes if other != c)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        report[c] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn
        }
        
    return accuracy, report, confusion_matrix

def main():
    parser = argparse.ArgumentParser(description="소비자 공정 Guard 파이프라인 자동 벤치마크 평가 도구")
    parser.add_argument("--sample_size", type=str, default="30", help="평가할 샘플 수 (숫자 또는 'all')")
    parser.add_argument("--seed", type=int, default=42, help="재현성을 위한 난수 시드값")
    parser.add_argument("--mock_rag", action="store_true", help="메모리 부족 시 무거운 RAG 모델 로딩을 생략하고 규칙 검증기만 단독 테스트")
    args = parser.parse_args()
    
    random.seed(args.seed)
    
    if not os.path.exists(DATA_FILE):
        print(f"❌ 데이터셋 파일이 존재하지 않습니다: {DATA_FILE}")
        return
        
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    total_records = len(dataset)
    print(f"📦 전체 데이터셋 로드 완료: 총 {total_records}건")
    
    # Stratified Sampling (층화 추출) 수행
    red_cases = [item for item in dataset if item["signal_color"] == "RED"]
    yellow_cases = [item for item in dataset if item["signal_color"] == "YELLOW"]
    green_cases = [item for item in dataset if item["signal_color"] == "GREEN"]
    
    if args.sample_size.lower() == "all":
        sample_size = total_records
        sampled_dataset = dataset
    else:
        sample_size = min(int(args.sample_size), total_records)
        
        # 비율 계산
        red_ratio = len(red_cases) / total_records
        yellow_ratio = len(yellow_cases) / total_records
        green_ratio = len(green_cases) / total_records
        
        red_n = max(1, round(sample_size * red_ratio))
        yellow_n = max(1, round(sample_size * yellow_ratio))
        green_n = max(1, sample_size - red_n - yellow_n)
        
        # 샘플링
        sampled_dataset = (
            random.sample(red_cases, min(red_n, len(red_cases))) +
            random.sample(yellow_cases, min(yellow_n, len(yellow_cases))) +
            random.sample(green_cases, min(green_n, len(green_cases)))
        )
        random.shuffle(sampled_dataset)
        
    print(f"🎯 층화 샘플링 수행 완료: 총 {len(sampled_dataset)}건 평가 시작")
    print(f"   - RED: {sum(1 for x in sampled_dataset if x['signal_color'] == 'RED')}건, "
          f"YELLOW: {sum(1 for x in sampled_dataset if x['signal_color'] == 'YELLOW')}건, "
          f"GREEN: {sum(1 for x in sampled_dataset if x['signal_color'] == 'GREEN')}건")
    if args.mock_rag:
        print("💡 [Mock RAG 모드 활성화] SentenceTransformer 모델 로딩을 생략하고 룰 검증기(validate_rules_node)만 단독 평가합니다.")
    print("=" * 60)
    
    y_true = []
    y_pred = []
    
    # 모듈은 필요할 때만 임포트하여 import-time 1455 에러 방지
    from modules.rule_validator import validate_rules_node
    if not args.mock_rag:
        try:
            from modules.rag_search import search_rag_node
        except ImportError as e:
            print(f"❌ RAG 모듈 임포트 실패 (메모리 부족 혹은 종속성 에러): {e}")
            print("💡 `--mock_rag` 옵션을 붙여 룰 검증기 단독 평가 모드로 다시 실행하세요.")
            sys.exit(1)
            
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("⚠️ [Warning] OPENAI_API_KEY가 설정되지 않아 로컬 Fallback 모드로 평가를 진행합니다.")
        
    for idx, item in enumerate(sampled_dataset, 1):
        query = item["query"]
        true_color = item["signal_color"]
        
        # RAG 검색 시뮬레이션용 state 빌드
        input_type = "CONTRACT"
        if any(w in query for w in ["광고", "선착순", "오늘만", "타이머", "부작용", "효능"]):
            input_type = "AD"
            
        state = {
            "file_path": "",
            "input_type": input_type,
            "raw_text": query,
            "retrieved_docs": [],
            "llm_analysis": "",
            "toxic_clauses": [],
            "signal_color": "",
            "report_draft": ""
        }
        
        try:
            # 1. RAG Node 실행 (Mock 모드 아닐 때만)
            if not args.mock_rag:
                state = search_rag_node(state)
            else:
                # Mock RAG docs 주입
                state["retrieved_docs"] = [
                    f"[참고 소비자원 유사 사례] {input_type} 관련 계약 해지 시 정당하지 않은 위약금/약관은 약관법에 따라 무효에 처해질 수 있습니다."
                ]
            
            # 2. Rule Validator Node 실행
            result = validate_rules_node(state)
            pred_color = result["signal_color"]
        except Exception as e:
            print(f"❌ [{idx}/{len(sampled_dataset)}] 평가 중 오류 발생: {e}")
            pred_color = "YELLOW"
            
        y_true.append(true_color)
        y_pred.append(pred_color)
        
        print(f"✅ [{idx}/{len(sampled_dataset)}] 질문: {query[:30]}...")
        print(f"   - 실제(True): {true_color:<6} | 예측(Pred): {pred_color:<6}")
        print("-" * 50)
        
    # 성능 메트릭 산출
    accuracy, metrics_report, confusion_matrix = calculate_metrics(y_true, y_pred)
    
    print("\n" + "=" * 60)
    print("📊 [벤치마크 평가 결과 보고서]")
    print("=" * 60)
    print(f"✔ 전체 정확도(Overall Accuracy): {accuracy * 100:.2f}%")
    print("\n🟢 클래스별 세부 지표:")
    print(f"   {'Class':<8} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("   " + "-" * 48)
    for c in ["RED", "YELLOW", "GREEN"]:
        m = metrics_report[c]
        print(f"   {c:<8} | {m['precision'] * 100:>8.2f}% | {m['recall'] * 100:>8.2f}% | {m['f1'] * 100:>8.2f}%")
        
    print("\n🟢 혼동 행렬 (Confusion Matrix):")
    print(f"   {'True \\ Pred':<12} | {'RED':<6} | {'YELLOW':<6} | {'GREEN':<6}")
    print("   " + "-" * 38)
    for t in ["RED", "YELLOW", "GREEN"]:
        print(f"   {t:<12} | {confusion_matrix[t]['RED']:<6} | {confusion_matrix[t]['YELLOW']:<6} | {confusion_matrix[t]['GREEN']:<6}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
