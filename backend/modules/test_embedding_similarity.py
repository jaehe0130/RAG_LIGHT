import sys
import os

backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Mock local_embedding_model to None to verify API fallback as well
import modules.validator.utils as val_utils
val_utils.local_embedding_model = None

from modules.validator.utils import get_embedding, cosine_similarity
from modules.validator.supervisor import is_clause_matched

def run_tests():
    # Force output encoding to UTF-8 to prevent cp949 encoding errors on Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=== [Test] Embedding Cosine Similarity Functionality ===")
    
    # 1. Test get_embedding API fallback
    txt1 = "환불 불가"
    txt2 = "해지 시 일체 반환되지 않음"
    txt3 = "양도 수수료 3만원 이하"
    
    print(f"Fetching embedding for: '{txt1}'")
    emb1 = get_embedding(txt1)
    print(f"Fetching embedding for: '{txt2}'")
    emb2 = get_embedding(txt2)
    print(f"Fetching embedding for: '{txt3}'")
    emb3 = get_embedding(txt3)
    
    if not emb1 or not emb2 or not emb3:
        print("[-] Failed: Could not retrieve embeddings from fallback API.")
        return
        
    print(f"Embedding dimensions: {len(emb1)}")
    
    # 2. Test cosine_similarity calculation
    sim_match = cosine_similarity(emb1, emb2)
    sim_mismatch = cosine_similarity(emb1, emb3)
    
    print(f"Similarity ('{txt1}' vs '{txt2}'): {sim_match:.4f}")
    print(f"Similarity ('{txt1}' vs '{txt3}'): {sim_mismatch:.4f}")
    
    # 3. Test is_clause_matched with embedding similarity fallback (Threshold = 0.70)
    llm_clause = {
        "clause": "계약 해지 조건",
        "reason": "해지 시 납부한 요금은 일체 반환되지 않습니다."
    }
    
    override_item = {
        "clause": "환불 불가 규정",
        "reason": "소비자 철회 권리 침해"
    }
    
    print("Testing is_clause_matched on semantic-only matching (Expect True)...")
    matched = is_clause_matched(llm_clause, override_item)
    print(f"is_clause_matched result: {matched}")
    
    # Also get individual embeddings and print similarity to see what it is
    emb_override = get_embedding(override_item["clause"])
    emb_llm = get_embedding(f"{llm_clause['clause']} {llm_clause['reason']}")
    sim_val = cosine_similarity(emb_override, emb_llm)
    print(f"Similarity of actual test case: {sim_val:.4f}")
    
    if matched:
        print("[SUCCESS] Clause matched semantically via embedding similarity!")
    else:
        print("[FAILED] Clause did not match.")

if __name__ == "__main__":
    run_tests()
