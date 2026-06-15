import os
from dotenv import load_dotenv
load_dotenv()
import json
import time
import os
import urllib3
urllib3.disable_warnings()
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from typing import List
from tqdm import tqdm
from modules.rag_search import retrieve_similar_cases
from modules.chat_agent import call_chat_llm

def evaluate_with_llm(query: str, expected_law: str, retrieved_docs: List[str]) -> bool:
    """LLM을 채점관으로 사용하여 검색된 문서가 정답 법령과 의미적으로 부합하는지 평가합니다."""
    combined_docs = "\n\n".join(retrieved_docs)
    
    prompt = f"""You are an expert legal evaluator (LLM-as-a-Judge).
Your task is to evaluate if a retrieval system found the correct legal context.

[User Query]
{query}

[Expected Legal Context (Ground Truth)]
{expected_law}

[Retrieved Documents]
{combined_docs}

Question: Do the [Retrieved Documents] provide the legal basis or precedent corresponding to the [Expected Legal Context] to answer the [User Query]? 
If the retrieved documents contain facts, articles, or precedents that match the intent of the Expected Legal Context, answer YES. If it is completely irrelevant, answer NO.

Reply with ONLY the word 'YES' or 'NO'.
"""
    try:
        api_key = os.getenv("OPENAI_API_KEY", "")
        messages = [{"role": "user", "content": prompt}]
        # LLM에게 채점 요청
        response = call_chat_llm(api_key, messages)
        if response:
            return "YES" in response.strip().upper()
        return False
    except Exception as e:
        print(f"LLM Eval Error: {e}")
        return False

def run_evaluation(dataset_path: str = "data/qa_dataset.json", sample_size: int = 50):
    print(f"Loading dataset from {dataset_path}...")
    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    if len(dataset) > sample_size:
        dataset = dataset[:sample_size]
    
    print(f"Starting LLM-based RAG Evaluation on {len(dataset)} samples...\n")
    
    hits = 0
    total_latency = 0
    
    for item in tqdm(dataset, desc="Evaluating (LLM as a Judge)"):
        query = item.get("query", "")
        expected_law = item.get("applicable_law", "")
        
        t0 = time.time()
        # 1. RAG Retrieve (기존 코어 로직)
        retrieved_docs = retrieve_similar_cases(query)
        latency = time.time() - t0
        total_latency += latency
        
        # 2. LLM Evaluation (스마트 채점)
        hit = evaluate_with_llm(query, expected_law, retrieved_docs)
                
        if hit:
            hits += 1
            
    avg_latency = total_latency / len(dataset)
    hit_rate = (hits / len(dataset)) * 100
    
    print("\n" + "="*55)
    print("🎯 RAG 자체 평가 결과 보고서 (LLM-as-a-Judge 도입)")
    print("="*55)
    print(f"총 평가 샘플 수: {len(dataset)}개")
    print(f"평균 검색 속도 (Latency): {avg_latency:.2f}초 / query")
    print(f"검색 정확도 (Hit Rate): {hit_rate:.1f}%")
    print("="*55)
    print("결과 해석:")
    print("- 기존 키워드 채점의 한계를 극복하고 LLM-as-a-Judge 기법을 적용한 실제 성능입니다.")
    print("- 의미 기반으로 평가된 Hit Rate이므로, 이 수치를 포트폴리오에 활용하시면 됩니다.")

if __name__ == "__main__":
    run_evaluation()
