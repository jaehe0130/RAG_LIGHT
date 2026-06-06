import React, { useState } from "react";
import ReportForm from "./components/ReportForm.jsx";
import ResultSummary from "./components/ResultSummary.jsx";
import TrafficLight from "./components/TrafficLight.jsx";
import TrendWidget from "./components/TrendWidget.jsx";
import UploadSection from "./components/UploadSection.jsx";
import { mockAnalysisResult } from "./mockData.js";

const ANALYSIS_STEPS = [
  "OCR로 문서를 읽는 중입니다",
  "위험 문구를 분리하는 중입니다",
  "유사 사례를 검색 중입니다"
];

function App() {
  const [analysisResult, setAnalysisResult] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [documentType, setDocumentType] = useState("terms");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState("");

  const handleAnalyze = ({ file, docType }) => {
    setUploadedFile(file);
    setDocumentType(docType);
    setIsAnalyzing(true);
    setAnalysisResult(null);

    // Mock 단계 표시: 백엔드 연결 전까지 실제 분석처럼 보이게 만든다.
    ANALYSIS_STEPS.forEach((step, index) => {
      window.setTimeout(() => setAnalysisStep(step), index * 520);
    });

    window.setTimeout(() => {
      setAnalysisResult({
        ...mockAnalysisResult,
        metadata: {
          file_name: file?.name || "mock-document.png",
          doc_type: docType
        }
      });
      setIsAnalyzing(false);
      setAnalysisStep("");
    }, 1700);

    // TODO: Replace mock data with backend API call when Team A completes routing.
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Team B Mock Frontend</p>
          <h1>불공정 약관 · 광고 OCR 판정</h1>
        </div>
        <div className="status-pill">Mock Mode</div>
      </header>

      <main className="workspace">
        <UploadSection
          documentType={documentType}
          uploadedFile={uploadedFile}
          isAnalyzing={isAnalyzing}
          analysisStep={analysisStep}
          onAnalyze={handleAnalyze}
        />

        {isAnalyzing && (
          <section className="analysis-loading" aria-live="polite">
            <div className="loading-spinner" />
            <strong>{analysisStep || ANALYSIS_STEPS[0]}</strong>
            <span>잠시 후 mock 분석 결과가 표시됩니다.</span>
          </section>
        )}

        {analysisResult && !isAnalyzing && (
          <section className="analysis-grid" aria-label="분석 결과">
            <TrafficLight signal={analysisResult.signal} />
            <ResultSummary result={analysisResult} />
            <TrendWidget statistics={analysisResult.statistics} />
            {analysisResult.signal === "RED" && (
              <ReportForm reportText={analysisResult.report_form} />
            )}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
