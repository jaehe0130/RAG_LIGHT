import React from "react";

function ResultSummary({ result }) {
  const highlightedText = buildHighlightedText(result.ocr_text, result.toxic_clauses);

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

      <div className="ocr-box">
        <span className="field-label">OCR 추출 텍스트</span>
        <p>{highlightedText}</p>
      </div>

      <div className="clause-list">
        <span className="field-label">문제 문구</span>
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

  // 긴 문장 안에서 독소 조항만 잘라 mark 태그로 감싼다.
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
