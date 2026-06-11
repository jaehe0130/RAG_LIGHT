import React from "react";

function ResultSummary({ result }) {
  const clauses = result.toxic_clauses || [];
  const highlightedText = buildHighlightedText(result.ocr_text, clauses);
  const ocrLength = result.ocr_text?.trim().length || 0;

  return (
    <section className="result-panel summary-panel" aria-label="OCR 결과 요약">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Summary</p>
          <h2>분석 요약</h2>
        </div>
      </div>

      <div className="summary-callout">
        <span>판정 설명</span>
        <p>{result.summary}</p>
      </div>

      <div className="warning-phrases">
        <span className="field-label">위험 또는 주의 문구</span>
        {clauses.length > 0 ? (
          <ul>
            {clauses.map((clause) => (
              <li key={clause}>{clause}</li>
            ))}
          </ul>
        ) : (
          <p className="empty-note">현재 응답에서 별도 위험 또는 주의 문구가 검출되지 않았습니다.</p>
        )}
      </div>

      <div className="ocr-quality">
        <div>
          <span>OCR 추출 글자 수</span>
          <strong>{ocrLength}</strong>
        </div>
        <div>
          <span>OCR 상태</span>
          <strong>{ocrLength > 0 ? "텍스트 추출됨" : "텍스트 없음"}</strong>
        </div>
      </div>

      <div className="reference-cases">
        <span className="field-label">유사 피해구제 및 의결서 사례 (RAG 검색 결과)</span>
        {result.reference_cases && result.reference_cases.length > 0 ? (
          <div className="cases-list" style={{ maxHeight: "200px", overflowY: "auto", background: "var(--color-surface)", padding: "12px", borderRadius: "8px", border: "1px solid var(--color-border)", fontSize: "0.85rem", color: "var(--color-text-secondary)" }}>
            {result.reference_cases.map((caseText, idx) => (
              <div key={idx} style={{ marginBottom: "12px", paddingBottom: "12px", borderBottom: "1px dashed var(--color-border)" }}>
                <strong>사례 {idx + 1}</strong>
                <p style={{ margin: "4px 0 0 0", whiteSpace: "pre-wrap" }}>{caseText}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-note">검색된 유사 사례가 없습니다.</p>
        )}
      </div>

      <div className="ocr-box">
        <span className="field-label">OCR 추출 텍스트</span>
        <p>{ocrLength > 0 ? highlightedText : "백엔드 OCR 결과가 비어 있습니다."}</p>
      </div>
    </section>
  );
}

function buildHighlightedText(text, clauses) {
  if (!text || clauses.length === 0) {
    return text;
  }

  const escapedClauses = clauses.map(escapeRegExp);
  const pattern = new RegExp(`(${escapedClauses.join("|")})`, "g");

  return text.split(pattern).map((part, index) => {
    if (clauses.includes(part)) {
      return (
        <mark key={`${part}-${index}`} className="clause-highlight">
          {part}
        </mark>
      );
    }

    return part;
  });
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export default ResultSummary;
