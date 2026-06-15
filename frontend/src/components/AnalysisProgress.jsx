import React from "react";

function AnalysisProgress({ currentStepIndex, isAnalyzing, hasFile }) {
  const progressPercent = isAnalyzing
    ? Math.max(24, Math.min(92, 24 + currentStepIndex * 17))
    : hasFile
      ? 100
      : 0;

  return (
    <section className={`progress-panel ${isAnalyzing ? "is-analyzing" : ""}`} aria-label="분석 진행 상태">
      <div className="section-heading">
        <p className="eyebrow">Analysis</p>
        <h2>문서를 분석하고 있어요</h2>
        <p>업로드한 문서의 주요 문구와 소비자 위험 신호를 차분히 확인하고 있습니다.</p>
      </div>

      <div className="analysis-document-card" aria-hidden="true">
        <div className="document-sheet">
          <span className="document-line line-long" />
          <span className="document-line" />
          <span className="document-line line-short" />
          <span className="document-block" />
          <span className="document-line" />
          {isAnalyzing && <span className="scan-line" />}
        </div>
        <div className="magnifier-icon">
          <span />
        </div>
      </div>

      <div className="analysis-progress-footer">
        <div className="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progressPercent}>
          <span style={{ width: `${progressPercent}%` }} />
        </div>
        <p>{hasFile ? "잠시만 기다려주세요. 결과가 준비되면 신호등 판정으로 안내합니다." : "분석할 문서를 먼저 업로드해주세요."}</p>
      </div>
    </section>
  );
}

export default AnalysisProgress;
