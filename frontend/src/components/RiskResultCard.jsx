import React from "react";

const RISK_COPY = {
  GREEN: {
    label: "안전",
    tone: "safe",
    title: "뚜렷한 위험 문구는 보이지 않습니다",
    nextAction: "그래도 계약 전 주요 조건은 한 번 더 확인해주세요.",
  },
  YELLOW: {
    label: "주의",
    tone: "warning",
    title: "확인이 필요한 문구가 있습니다",
    nextAction: "환불, 위약금, 제한 조건을 다시 확인하고 관련 화면을 보관해주세요.",
  },
  RED: {
    label: "위험",
    tone: "danger",
    title: "소비자에게 불리할 수 있는 문구가 보입니다",
    nextAction: "계약 전이라면 신중히 검토하고, 피해가 있다면 관계 기관 상담을 권장합니다.",
  },
};

function RiskResultCard({ result, onAskQuestion }) {
  const signal = result?.signal || "YELLOW";
  const copy = RISK_COPY[signal] || RISK_COPY.YELLOW;
  const clauses = result?.toxic_clauses || [];
  const primaryClause = clauses[0] || "특정 위험 문구가 별도로 표시되지 않았습니다.";

  return (
    <section className={`risk-result-card ${copy.tone}`} aria-label="신호등 분석 결과">
      <div className="risk-topline">
        <span className="risk-light" aria-hidden="true" />
        <div>
          <p className="eyebrow">Result</p>
          <h2>{copy.label} 판정</h2>
        </div>
      </div>

      <div className="risk-content">
        <p className="risk-title">{copy.title}</p>

        <div className="risk-field">
          <span>핵심 위험 문구</span>
          <strong>{primaryClause}</strong>
        </div>

        <div className="risk-field">
          <span>쉬운 설명</span>
          <p>{result?.summary || copy.nextAction}</p>
        </div>
      </div>

      <div className="risk-actions">
        <button type="button" onClick={() => onAskQuestion("왜 이런 판정인가요?")}>
          이유 물어보기
        </button>
        <button type="button" className="secondary-action" onClick={() => onAskQuestion("소비자가 할 수 있는 조치는?")}>
          다음 행동 보기
        </button>
      </div>
    </section>
  );
}

export default RiskResultCard;
