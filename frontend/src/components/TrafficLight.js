import React from 'react';

function TrafficLight({ color, clauses, stats }) {
  // 3색 신호등 결과 및 유사 피해 트렌드 시각화 컴포넌트
  
  const getLightColor = () => {
    if(color === 'RED') return '🔴 위험 (RED)';
    if(color === 'YELLOW') return '🟡 주의 (YELLOW)';
    return '🟢 안전 (GREEN)';
  };

  return (
    <div className="traffic-light-result" style={{ marginTop: '2rem', padding: '1rem', background: '#f9f9f9' }}>
      <h2>판정 결과: {getLightColor()}</h2>
      
      {/* 백엔드 검증 노드에서 뽑아낸 독소 조항 하이라이트 */}
      <div className="toxic-clauses">
        <h3>🔍 독소 조항 / 기만 행위 하이라이트</h3>
        <ul>
          {/* TODO: clauses 배열을 순회하며 하이라이트 형광펜 효과 적용하여 렌더링 */}
          <li>예시: 제5조 위약금 - 과도한 위약금 청구 우려</li>
        </ul>
      </div>

      {/* 팀원 C의 RAG 데이터로 만들어진 맞춤형 트렌드 */}
      <div className="trend-statistics" style={{ marginTop: '1.5rem' }}>
        <h3>📊 맞춤형 피해 사례 트렌드</h3>
        <p><strong>해당 업종:</strong> {stats.industry}</p>
        <p><strong>분쟁 발생률:</strong> {stats.dispute_rate}%</p>
        <p><strong>최근 나와 유사한 피해 접수 건수:</strong> <span style={{ color: 'red', fontWeight: 'bold' }}>{stats.similar_cases_count}건</span></p>
        
        {/* TODO: Recharts 등을 활용하여 시각화된 파이차트/바차트 구현 */}
        <div style={{ height: '100px', background: '#ddd', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          차트 시각화 영역 (팀원 B 작업)
        </div>
      </div>
    </div>
  );
}

export default TrafficLight;
