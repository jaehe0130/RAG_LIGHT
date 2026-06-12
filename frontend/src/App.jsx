import React, { useEffect, useState } from "react";
import { analyzeDocument } from "./api/analyzeClient.js";
import AnalysisProgress from "./components/AnalysisProgress.jsx";
import ChatbotPanel from "./components/ChatbotPanel.jsx";
import RiskResultCard from "./components/RiskResultCard.jsx";
import UploadPanel from "./components/UploadPanel.jsx";

const PROGRESS_STEP_COUNT = 5;

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [docType, setDocType] = useState("terms");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progressIndex, setProgressIndex] = useState(0);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [chatQuestion, setChatQuestion] = useState("");
  const [isChatOpen, setIsChatOpen] = useState(false);

  useEffect(() => {
    if (!isAnalyzing) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setProgressIndex((current) => Math.min(current + 1, PROGRESS_STEP_COUNT - 1));
    }, 900);

    return () => window.clearInterval(timer);
  }, [isAnalyzing]);

  const handleAnalyze = async () => {
    if (!selectedFile || isAnalyzing) {
      return;
    }

    setIsAnalyzing(true);
    setProgressIndex(1);
    setErrorMessage("");
    setAnalysisResult(null);

    try {
      const apiResult = await analyzeDocument({ file: selectedFile, docType });
      const viewModel = mapApiResultToViewModel(apiResult, selectedFile, docType);

      setProgressIndex(PROGRESS_STEP_COUNT - 1);
      setAnalysisResult(viewModel);

      if (viewModel.ocr_text.trim().length > 0 && viewModel.ocr_text.trim().length < 20) {
        setErrorMessage("문서 인식 결과가 부족합니다. 더 선명한 이미지로 다시 시도해주세요.");
      }
    } catch (error) {
      console.error("문서 분석 실패:", error);
      setErrorMessage("문서 분석에 실패했습니다. 파일 형식과 백엔드 서버 실행 상태를 확인해주세요.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const askChatbot = (question) => {
    setChatQuestion(question);
    setIsChatOpen(true);
  };

  return (
    <div className="app-shell">
      <header className="hero-header">
        <div>
          <p className="eyebrow">공정거래 문서 분석</p>
          <h1>소비자에게 불리할 수 있는 문구를 쉽게 확인하세요</h1>
          <p>
            약관, 광고 캡처, 계약서 문서를 올리면 위험 문구를 찾고 쉬운 설명과 다음 행동을 안내합니다.
          </p>
        </div>
      </header>

      <main className="app-layout">
        <div className="main-column">
          <section className="top-grid">
            <UploadPanel
              selectedFile={selectedFile}
              docType={docType}
              isAnalyzing={isAnalyzing}
              errorMessage={errorMessage}
              onFileChange={(file) => {
                setSelectedFile(file);
                setProgressIndex(file ? 1 : 0);
                setErrorMessage("");
              }}
              onDocTypeChange={setDocType}
              onAnalyze={handleAnalyze}
            />

            <AnalysisProgress currentStepIndex={progressIndex} isAnalyzing={isAnalyzing} hasFile={Boolean(selectedFile)} />
          </section>

          {analysisResult ? (
            <section className="results-area" aria-label="분석 결과">
              <RiskResultCard result={analysisResult} onAskQuestion={askChatbot} />
              <ResultDetails result={analysisResult} />
            </section>
          ) : (
            <section className="empty-result-panel">
              <h2>분석 결과가 여기에 표시됩니다</h2>
              <p>문서를 업로드하고 “문서 분석하기”를 누르면 신호등 결과와 쉬운 설명을 확인할 수 있습니다.</p>
            </section>
          )}
        </div>

        <aside className="chat-side">
          <ChatbotPanel analysisResult={analysisResult} externalQuestion={chatQuestion} onExternalQuestionHandled={() => setChatQuestion("")} />
        </aside>
      </main>

      <button type="button" className="chat-fab" onClick={() => setIsChatOpen(true)}>
        상담 도우미
      </button>

      {isChatOpen && (
        <div className="chat-modal-backdrop" role="dialog" aria-modal="true" aria-label="소비자 상담 도우미">
          <ChatbotPanel
            analysisResult={analysisResult}
            externalQuestion={chatQuestion}
            onExternalQuestionHandled={() => setChatQuestion("")}
            variant="modal"
            onClose={() => setIsChatOpen(false)}
          />
        </div>
      )}

      <footer className="service-disclaimer">
        이 서비스는 소비자에게 불리할 수 있는 문구를 쉽게 확인하기 위한 참고용 도구입니다. 최종 판단이나 법적 조치는
        관련 기관 상담을 통해 확인해주세요.
      </footer>
    </div>
  );
}

function ResultDetails({ result }) {
  return (
    <section className="result-details">
      <div className="detail-card">
        <h2>관련 사례 기반 설명</h2>
        {result.reference_cases.length > 0 ? (
          <ul className="case-list">
            {result.reference_cases.slice(0, 3).map((caseText, index) => (
              <li key={`${index}-${caseText.slice(0, 24)}`}>{caseText}</li>
            ))}
          </ul>
        ) : (
          <p>아직 표시할 관련 사례가 없습니다.</p>
        )}
      </div>

      <div className="detail-card">
        <h2>추출된 문구</h2>
        <p className="extracted-text">{result.ocr_text || "추출된 문구가 없습니다."}</p>
      </div>

      <details className="technical-details">
        <summary>상세 보기</summary>
        <dl>
          <div>
            <dt>분석 상태</dt>
            <dd>{result.status || "확인됨"}</dd>
          </div>
          <div>
            <dt>문서 종류</dt>
            <dd>{result.docTypeLabel}</dd>
          </div>
          <div>
            <dt>인식 품질 참고</dt>
            <dd>{result.ocr_text.length > 20 ? "분석 가능한 문구가 추출되었습니다." : "문구가 짧아 재촬영이 필요할 수 있습니다."}</dd>
          </div>
        </dl>
      </details>
    </section>
  );
}

function mapApiResultToViewModel(apiResult, file, docType) {
  const analysis = apiResult.analysis || {};
  const signal = normalizeSignal(analysis.signal_color);
  const clauses = normalizeClauses(analysis.toxic_clauses || []);

  return {
    signal,
    riskLabel: signalToLabel(signal),
    summary: analysis.main_warning || "분석 결과 설명이 아직 없습니다.",
    ocr_text: apiResult.ocr_text || "",
    toxic_clauses: clauses,
    report_form: apiResult.report_form?.content || "",
    reference_cases: apiResult.reference_cases || [],
    status: apiResult.status || "",
    fileName: file?.name || "",
    docType,
    docTypeLabel: docType === "terms" ? "약관·계약서" : "광고·캡처",
  };
}

function normalizeSignal(signal) {
  const upperSignal = String(signal || "").toUpperCase();
  if (upperSignal === "GREEN" || upperSignal === "SAFE") {
    return "GREEN";
  }
  if (upperSignal === "RED" || upperSignal === "DANGER") {
    return "RED";
  }
  return "YELLOW";
}

function signalToLabel(signal) {
  if (signal === "GREEN") {
    return "안전";
  }
  if (signal === "RED") {
    return "위험";
  }
  return "주의";
}

function normalizeClauses(clauses) {
  return clauses
    .map((clause) => {
      if (typeof clause === "string") {
        return clause;
      }
      return clause?.text || clause?.clause || clause?.content || "";
    })
    .filter(Boolean);
}

export default App;
