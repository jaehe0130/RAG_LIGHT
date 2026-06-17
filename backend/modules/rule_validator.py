"""
This module serves as the backwards-compatible entry point for rule validation,
delegating the actual implementation to the modular modules.validator package.
"""

from modules.validator.subgraph import validate_rules_node, classifier_node
from modules.validator.classifier import ClassifierAgent
from modules.validator.auditor import (
    parse_korean_number_to_int,
    extract_penalty_percentages,
    extract_krw_amount,
    extract_refund_days,
    run_quantitative_checks,
    RuleAuditor,
    rule_auditor_node
)
from modules.validator.analysts import LegalAnalyst, legal_analyst_node
from modules.validator.supervisor import (
    check_discrepancy,
    consensus_supervisor_node
)
