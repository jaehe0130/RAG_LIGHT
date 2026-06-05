import React, { useState } from "react";
import ReportForm from "./components/ReportForm.jsx";
import ResultSummary from "./components/ResultSummary.jsx";
import TrafficLight from "./components/TrafficLight.jsx";
import TrendWidget from "./components/TrendWidget.jsx";
import UploadSection from "./components/UploadSection.jsx";
import { mockAnalysisResult } from "./mockData.js";

function App() {
  const [analysisResult, setAnalysisResult] = useState(mockAnalysisResult);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [documentType, setDocumentType] = useState("terms");

  const handleAnalyze = ({ file, docType }) => {
    setUploadedFile(file);
    setDocumentType(docType);
    setAnalysisResult({
      ...mockAnalysisResult,
      metadata: {
        file_name: file?.name || "mock-document.png",
        doc_type: docType
      }
    });

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
          onAnalyze={handleAnalyze}
        />

        {analysisResult && (
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
