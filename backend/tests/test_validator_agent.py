import os
import sys
from unittest.mock import MagicMock

# Prevent loading heavy local models in test scripts to avoid virtual memory exhaustion
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['qdrant_client'] = MagicMock()

from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from modules.rule_validator import validate_rules_node

def test_sports_contract():
    print("\n=== Testing Gym Contract (SPORTS) ===")
    test_state = {
        "raw_text": "헬스장 이용약관: 중도 해지 시 위약금은 총 결제 금액의 10.5%로 부과하며, 회원권 양도 수수료는 50,000원입니다. 이용자는 어떠한 경우에도 환불이 불가합니다.",
        "input_type": "CONTRACT",
        "classified_type": "SPORTS",
        "retrieved_docs": [],
        "retrieved_ftc_docs": [],
        "retrieved_kca_docs": []
    }
    
    result = validate_rules_node(test_state)
    print("Test Result:")
    print("  Signal Color:", result.get("signal_color"))
    print("  LLM Analysis:", result.get("llm_analysis"))
    print("  Toxic Clauses:")
    for c in result.get("toxic_clauses", []):
        print(f"    - Clause: {c.get('clause')} | Reason: {c.get('reason')}")

def test_ecommerce_contract():
    print("\n=== Testing E-commerce Contract (ECOMMERCE) ===")
    test_state = {
        "raw_text": "온라인 쇼핑몰 구매약관: 단순 변심으로 인한 교환 및 환불은 제품 배송 후 3일 이내에만 가능합니다. 또한 상품 박스를 개봉 시 환불이 불가합니다. 취소 수수료는 15% 청구됩니다.",
        "input_type": "CONTRACT",
        "classified_type": "ECOMMERCE",
        "retrieved_docs": [],
        "retrieved_ftc_docs": [],
        "retrieved_kca_docs": []
    }
    
    result = validate_rules_node(test_state)
    print("Test Result:")
    print("  Signal Color:", result.get("signal_color"))
    print("  LLM Analysis:", result.get("llm_analysis"))
    print("  Toxic Clauses:")
    for c in result.get("toxic_clauses", []):
        print(f"    - Clause: {c.get('clause')} | Reason: {c.get('reason')}")

if __name__ == "__main__":
    test_sports_contract()
    test_ecommerce_contract()
