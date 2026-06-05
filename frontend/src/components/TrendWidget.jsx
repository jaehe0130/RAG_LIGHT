import React from "react";

function TrendWidget({ statistics }) {
  return (
    <section className="result-panel trend-panel" aria-label="유사 피해 통계">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Trend</p>
          <h2>유사 피해 통계</h2>
        </div>
      </div>

      <div className="stat-grid">
        <article className="stat-card">
          <span>유사 피해 사례</span>
          <strong>{statistics.similar_case_count}</strong>
          <small>최근 매칭 건수</small>
        </article>
        <article className="stat-card">
          <span>분쟁 비율</span>
          <strong>{statistics.dispute_rate}%</strong>
          <small>동일 유형 기준</small>
        </article>
      </div>
    </section>
  );
}

export default TrendWidget;
