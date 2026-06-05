import React from "react";

function ResultSummary({ result }) {
  const highlightedText = buildHighlightedText(result.ocr_text, result.toxic_clauses);

  return (
    <section className="result-panel summary-panel" aria-label="OCR 결과 요약">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Summary</p>
          <h2>OCR 분석 요약</h2>
        </div>
      </div>

      <p className="summary-copy">{result.summary}</p>

      <div className="ocr-box">
        <span className="field-label">OCR 추출 텍스트</span>
        <p>{highlightedText}</p>
      </div>

      <div className="clause-list">
        <span className="field-label">위험 또는 주의 문구</span>
        <ul>
          {result.toxic_clauses.map((clause) => (
            <li key={clause}>{clause}</li>
          ))}
        </ul>
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
