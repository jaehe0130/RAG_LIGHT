export const mockAnalysisResult = {
  signal: "RED",
  summary: "환불 불가 조항이 소비자에게 일방적으로 불리할 가능성이 있습니다.",
  ocr_text: "계약 해지 시 위약금 50%가 부과되며 환불은 불가합니다.",
  toxic_clauses: ["환불 불가", "계약 해지 시 위약금 50%"],
  statistics: {
    similar_case_count: 37,
    dispute_rate: 68
  },
  report_form:
    "신고서 초안 내용\n\n1. 문제 조항: 계약 해지 시 위약금 50%가 부과되며 환불은 불가합니다.\n2. 신고 사유: 소비자에게 과도하게 불리한 환불 제한 및 위약금 조항으로 의심됩니다.\n3. 요청 사항: 해당 약관 또는 광고 문구의 불공정성 검토를 요청합니다."
};
