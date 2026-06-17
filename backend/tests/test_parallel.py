import os
import sys
import asyncio
import time
from unittest.mock import MagicMock

# 1. CLI 테스트 환경에서 무거운 ML 모델 로딩을 막기 위한 Mocking 적용
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['qdrant_client'] = MagicMock()

# backend 디렉토리를 PATH에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. OCR 모듈의 실제 실행을 막고 가상의 약관 텍스트를 반환하도록 Mocking
import modules.ocr
modules.ocr.run_ocr_node = MagicMock(return_value={
    "raw_text": "헬스장 이용약관: 중도 해지 시 위약금은 총 결제 금액의 10.5%로 부과하며, 회원권 양도 수수료는 50,000원입니다. 이용자는 어떠한 경우에도 환불이 불가합니다."
})

# 3. RAG Search 노드의 실행 과정을 시각화하기 위해 함수 패칭 (시작/종료 시간에 타임스탬프 표시)
import modules.rag_search
original_search_rag_node = modules.rag_search.search_rag_node

def patched_search_rag_node(state):
    t_start = time.time()
    print(f"\n🚀 [Parallel RUN] >>> RAG Search 노드 시작 (Timestamp: {t_start:.4f})")
    
    # 실제 Qdrant 벡터 검색 대신 0.8초 딜레이를 주어 동시성 가동 확인용 시뮬레이션
    time.sleep(0.8)
    
    result = original_search_rag_node(state)
    t_end = time.time()
    print(f"✅ [Parallel RUN] <<< RAG Search 노드 완료 (Timestamp: {t_end:.4f}, 소요시간: {t_end - t_start:.4f}초)")
    return result

modules.rag_search.search_rag_node = patched_search_rag_node

# main.py 임포트 (패칭된 상태의 노드들을 가져가 그래프 구성)
from main import compiled_graph

async def test_main_pipeline():
    print("\n" + "="*60)
    print("🛡️ [Main Graph] 비동기 병렬(Classifier & RAG) 테스트 시작...")
    print("="*60)
    
    initial_state = {
        "file_path": "dummy_contract.png",
        "input_type": "CONTRACT",
        "raw_text": "",
        "retrieved_docs": [],
        "llm_analysis": "",
        "toxic_clauses": [],
        "signal_color": "",
        "report_draft": "",
        "classified_type": "",
    }
    
    pipeline_t0 = time.time()
    # main.py의 ainvoke를 가동하여 병렬 노드를 비동기적으로 실행
    final_output = await compiled_graph.ainvoke(initial_state)
    pipeline_t1 = time.time()
    
    print("\n" + "="*60)
    print("🎉 전체 파이프라인 완료!")
    print(f"⏱️ 총 소요시간: {pipeline_t1 - pipeline_t0:.3f}초")
    print(f"📂 최종 문서 분류 결과: {final_output.get('classified_type')}")
    print(f"🚦 최종 신호등 판정: {final_output.get('signal_color')}")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_main_pipeline())
