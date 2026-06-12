import React from "react";

const STEPS = ["문서 업로드 완료", "OCR 텍스트 추출 중", "위험 문구 분석 중", "관련 사례 비교 중", "결과 정리 중"];

function AnalysisProgress({ currentStepIndex, isAnalyzing, hasFile }) {
  return (
    <section className="progress-panel" aria-label="분석 진행 상태">
      <div className="section-heading">
        <p className="eyebrow">Progress</p>
        <h2>분석 진행 상태</h2>
      </div>

      <ol className="progress-steps">
        {STEPS.map((step, index) => {
          const isDone = hasFile && index < currentStepIndex;
          const isActive = isAnalyzing && index === currentStepIndex;
          const isReadyUpload = hasFile && !isAnalyzing && index === 0;

          return (
            <li key={step} className={`${isDone || isReadyUpload ? "is-done" : ""} ${isActive ? "is-active" : ""}`}>
              <span>{index + 1}</span>
              <strong>{step}</strong>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default AnalysisProgress;
