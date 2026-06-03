import React, { useState } from 'react';
import UploadSection from './components/UploadSection';
import TrafficLight from './components/TrafficLight';
import ReportForm from './components/ReportForm';

function App() {
  const [analysisResult, setAnalysisResult] = useState(null);

  // 백엔드 API 연동 함수 뼈대 (팀원 B 작성 구간)
  const handleUpload = async (file, inputType) => {
    console.log("백엔드(/api/analyze)로 파일 전송 로직 구현", file, inputType);
    
    // TODO: axios 또는 fetch를 사용하여 백엔드의 FastAPI로 파일 전송
    // const formData = new FormData();
    // formData.append("file", file);
    // formData.append("input_type", inputType);
    
    // 임시 모의 데이터 셋팅
    // setAnalysisResult(mockData);
  };

  return (
    <div className="App">
      <header>
        <h1>찰칵! 소비자 공정 Guard</h1>
        <p>공정 소비 신호등 AI 서비스</p>
      </header>
      
      <main>
        {/* 1. 업로드 영역 (드래그 앤 드롭) */}
        <UploadSection onUpload={handleUpload} />

        {/* 2. 결과 시각화 및 신고서 영역 (분석 결과가 반환되었을 때만 렌더링) */}
        {analysisResult && (
          <section className="results-container">
            {/* 3색 신호등 및 트렌드 위젯 컴포넌트 */}
            <TrafficLight 
              color={analysisResult.analysis.signal_color} 
              clauses={analysisResult.analysis.toxic_clauses} 
              stats={analysisResult.statistics} 
            />
            
            {/* RED 판정 시에만 관공서 신고서 원스톱 연계 활성화 */}
            {analysisResult.analysis.signal_color === 'RED' && (
              <ReportForm reportData={analysisResult.report_form} />
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
