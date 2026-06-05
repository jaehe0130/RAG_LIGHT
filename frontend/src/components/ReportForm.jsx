import React, { useState } from "react";

function ReportForm({ reportText }) {
  const [copyState, setCopyState] = useState("idle");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(reportText);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1600);
    } catch {
      setCopyState("failed");
    }
  };

  return (
    <section className="result-panel report-panel" aria-label="신고서 초안">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Report</p>
          <h2>신고서 초안</h2>
        </div>
        <span className="danger-chip">RED 전용</span>
      </div>

      <textarea readOnly value={reportText} aria-label="신고서 초안 내용" />

      <div className="button-row">
        <button type="button" onClick={handleCopy}>
          문서 복사하기
        </button>
        <button type="button" className="secondary-action" disabled>
          PDF 다운로드
        </button>
      </div>

      {copyState === "copied" && <p className="feedback success">신고서 초안이 복사되었습니다.</p>}
      {copyState === "failed" && <p className="feedback">클립보드 복사에 실패했습니다.</p>}

      {/* TODO: Add PDF download after report export policy and library choice are finalized. */}
    </section>
  );
}

export default ReportForm;
