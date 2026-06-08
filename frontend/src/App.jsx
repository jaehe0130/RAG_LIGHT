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
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [documentType, setDocumentType] = useState("terms");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState("");

  const handleAnalyze = async ({ files, docType }) => {
    const nextFiles = files || [];
    setUploadedFiles(nextFiles);
    setDocumentType(docType);
    setIsAnalyzing(true);
    setAnalysisResult(null);

    // 백엔드 연결 전까지 실제 분석처럼 보이도록 단계 문구를 순서대로 보여준다.
    ANALYSIS_STEPS.forEach((step, index) => {
      window.setTimeout(() => setAnalysisStep(step), index * 520);
    });

    if (nextFiles.length === 0) {
      setIsAnalyzing(false);
      return;
    }

    try {
      const formData = new FormData();
      formData.append("file", nextFiles[0]);
      formData.append("input_type", docType);

      const response = await fetch("http://localhost:8000/api/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("서버 응답 오류");
      }

      const resultData = await response.json();
      
      setAnalysisResult({
        signal: resultData.analysis.signal_color || "RED",
        summary: resultData.analysis.main_warning || "분석 완료",
        ocr_text: resultData.ocr_text || "",
        toxic_clauses: resultData.analysis.toxic_clauses || [],
        statistics: {
          similar_case_count: resultData.statistics?.similar_cases_count || 0,
          dispute_rate: resultData.statistics?.dispute_rate || 0
        },
        report_form: resultData.report_form?.content || "",
        metadata: {
          file_names: nextFiles.map((file) => file.name),
          doc_type: docType
        }
      });
    } catch (error) {
      console.error("분석 중 오류 발생:", error);
      alert("분석 요청 중 오류가 발생했습니다.");
    } finally {
      setIsAnalyzing(false);
      setAnalysisStep("");
    }
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
          uploadedFiles={uploadedFiles}
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
