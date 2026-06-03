import React from 'react';

function ReportForm({ reportData }) {
  // RED 판정 시 등장하는 관공서 신고서 원클릭 연계 컴포넌트
  
  return (
    <div className="report-form-container" style={{ marginTop: '2rem', border: '1px solid red', padding: '1rem' }}>
      <h2>🚨 원스톱 피해 구제 연계</h2>
      <p>위험 등급이 감지되었습니다. 아래 생성된 초안을 활용해 관공서에 바로 신고하세요.</p>
      
      <div className="report-preview" style={{ background: '#fff', padding: '1rem', border: '1px solid #ccc' }}>
        <h3>{reportData.title}</h3>
        <textarea 
          readOnly 
          value={reportData.content} 
          style={{ width: '100%', minHeight: '150px' }} 
        />
      </div>
      
      <div className="action-buttons" style={{ marginTop: '1rem', display: 'flex', gap: '10px' }}>
        <button onClick={() => alert("클립보드에 복사되었습니다!")}>
          📄 문서 복사하기
        </button>
        <button onClick={() => alert("PDF 다운로드 로직 시작!")}>
          📥 PDF 서식 다운로드
        </button>
      </div>
    </div>
  );
}

export default ReportForm;
