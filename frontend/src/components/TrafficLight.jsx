import React from "react";

const LIGHTS = [
  { key: "GREEN", label: "안전", className: "green" },
  { key: "YELLOW", label: "주의", className: "yellow" },
  { key: "RED", label: "위험", className: "red" }
];

function TrafficLight({ signal }) {
  return (
    <section className="result-panel traffic-panel" aria-label="신호등 판정">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Signal</p>
          <h2>현재 판정</h2>
        </div>
        <span className={`signal-badge ${signal.toLowerCase()}`}>{signal}</span>
      </div>

      <div className="traffic-light">
        {LIGHTS.map((light) => (
          <div
            key={light.key}
            className={`traffic-dot ${light.className} ${signal === light.key ? "is-active" : ""}`}
            aria-label={`${light.label} ${signal === light.key ? "활성" : "비활성"}`}
          />
        ))}
      </div>

      <div className="light-labels">
        {LIGHTS.map((light) => (
          <span key={light.key} className={signal === light.key ? "is-active" : ""}>
            {light.label}
          </span>
        ))}
      </div>
    </section>
  );
}

export default TrafficLight;
