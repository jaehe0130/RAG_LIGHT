import React, { useState } from "react";
import ReportForm from "./components/ReportForm.jsx";
import ResultSummary from "./components/ResultSummary.jsx";
import TrafficLight from "./components/TrafficLight.jsx";
import TrendWidget from "./components/TrendWidget.jsx";
import UploadSection from "./components/UploadSection.jsx";

const API_URL = "http://localhost:8000/api/analyze";

const ANALYSIS_STEPS = [
  "OCR로 문서를 읽는 중입니다",
  "유사 사례를 검색 중입니다",
  "최종 판정을 정리하는 중입니다"
];

function App() {
  const [analysisResult, setAnalysisResult] = useState(null);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [documentType, setDocumentType] = useState("terms");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const handleAnalyze = async ({ files, docType }) => {
    const nextFiles = files || [];
    setUploadedFiles(nextFiles);
    setDocumentType(docType);
    setIsAnalyzing(true);
    setAnalysisResult(null);
    setErrorMessage("");

    ANALYSIS_STEPS.forEach((step, index) => {
      window.setTimeout(() => setAnalysisStep(step), index * 520);
    });

    if (nextFiles.length === 0) {
      setIsAnalyzing(false);
      setErrorMessage("분석할 파일을 먼저 선택해 주세요.");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("file", nextFiles[0]);
      formData.append("input_type", docType);

      const response = await fetch(API_URL, {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error(`API 응답 오류: ${response.status}`);
      }

      const apiResult = await response.json();
      setAnalysisResult(mapApiResultToViewModel(apiResult, nextFiles, docType));
    } catch (error) {
      console.error("분석 요청 중 오류 발생:", error);
      setErrorMessage("백엔드 API 분석 요청에 실패했습니다. 서버 실행 상태와 업로드 파일을 확인해 주세요.");
    } finally {
      setIsAnalyzing(false);
      setAnalysisStep("");
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Team B Frontend</p>
          <h1>불공정 약관 · 광고 OCR 판정</h1>
        </div>
        <div className="status-pill api">API Mode</div>
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
            <span>백엔드 OCR API 응답을 기다리고 있습니다.</span>
          </section>
        )}

        {errorMessage && !isAnalyzing && (
          <section className="result-panel error-panel" aria-live="polite">
            <p className="eyebrow">Error</p>
            <h2>분석 실패</h2>
            <p>{errorMessage}</p>
          </section>
        )}

        {analysisResult && !isAnalyzing && (
          <section className="analysis-grid" aria-label="분석 결과">
            <div className="result-stack">
              <TrafficLight signal={analysisResult.signal} />
              <TrendWidget statistics={analysisResult.statistics} />
              <ReportForm reportText={analysisResult.report_form} />
            </div>
            <ResultSummary result={analysisResult} />
          </section>
        )}
      </main>
    </div>
  );
}

function mapApiResultToViewModel(apiResult, files, docType) {
  const analysis = apiResult.analysis || {};
  const statistics = apiResult.statistics || {};
  const reportForm = apiResult.report_form || {};
  const toxicClauses = normalizeClauses(analysis.toxic_clauses || []);

  return {
    signal: analysis.signal_color || "YELLOW",
    summary: analysis.main_warning || "백엔드 분석 결과가 도착했습니다.",
    ocr_text: apiResult.ocr_text || "",
    toxic_clauses: toxicClauses,
    statistics: {
      similar_case_count: statistics.similar_cases_count || statistics.similar_case_count || 0,
      dispute_rate: statistics.dispute_rate || 0,
      industry: statistics.industry || ""
    },
    report_form: reportForm.content || "신고서 초안 내용이 없습니다.",
    metadata: {
      file_names: files.map((file) => file.name),
      analyzed_file_name: files[0]?.name || "",
      doc_type: docType,
      status: apiResult.status || ""
    }
  };
}

function normalizeClauses(clauses) {
  return clauses
    .map((clause) => {
      if (typeof clause === "string") {
        return clause;
      }

      return clause?.text || clause?.clause || clause?.content || JSON.stringify(clause);
    })
    .filter(Boolean);
}

export default App;
