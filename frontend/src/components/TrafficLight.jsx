import React from "react";

const LIGHTS = [
  { key: "GREEN", label: "안전", description: "문제 가능성 낮음", className: "green" },
  { key: "YELLOW", label: "주의", description: "추가 확인 필요", className: "yellow" },
  { key: "RED", label: "위험", description: "신고서 검토 권장", className: "red" }
];

function TrafficLight({ signal }) {
  const activeLight = LIGHTS.find((light) => light.key === signal);

  return (
    <section className="result-panel traffic-panel" aria-label="신호등 판정">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Signal</p>
          <h2>현재 판정</h2>
        </div>
        <span className={`signal-badge ${signal.toLowerCase()}`}>{signal}</span>
      </div>

      <div className="traffic-card-list">
        {LIGHTS.map((light) => {
          const isActive = signal === light.key;

          return (
            <article
              key={light.key}
              className={`traffic-card ${light.className} ${isActive ? "is-active" : ""}`}
              aria-current={isActive ? "true" : undefined}
            >
              <span className="traffic-dot" />
              <div>
                <strong>{light.label}</strong>
                <small>{light.description}</small>
              </div>
            </article>
          );
        })}
      </div>

      <p className="signal-summary">
        현재 문서는 <strong>{activeLight?.label}</strong> 단계로 분류되었습니다.
      </p>
    </section>
  );
}

export default TrafficLight;
