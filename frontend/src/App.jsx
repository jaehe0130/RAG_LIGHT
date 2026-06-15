import React, { useEffect, useState } from "react";
import { analyzeDocument } from "./api/analyzeClient.js";
import AnalysisProgress from "./components/AnalysisProgress.jsx";
import ChatbotPanel from "./components/ChatbotPanel.jsx";
import ReportForm from "./components/ReportForm.jsx";
import RiskResultCard from "./components/RiskResultCard.jsx";
import UploadPanel from "./components/UploadPanel.jsx";

const PROGRESS_STEP_COUNT = 5;

function App() {
  const [view, setView] = useState("landing");
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
        setErrorMessage("문서 인식 결과가 충분하지 않습니다. 글자가 선명한 이미지로 다시 시도해주세요.");
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

  if (view === "landing") {
    return <LandingPage onStart={() => setView("analysis")} />;
  }

  return (
    <div className="app-shell analysis-shell">
      <header className="hero-header analysis-header">
        <div>
          <p className="eyebrow">공정거래 문서 분석</p>
          <h1>소비자에게 불리할 수 있는 문구를 쉽고 정확하게 확인하세요</h1>
          <p>약관, 광고 캡처, 계약서 이미지를 올리면 위험 문구를 찾아 신호등 판정과 다음 조치를 안내합니다.</p>
        </div>
        <button type="button" className="ghost-action" onClick={() => setView("landing")}>
          서비스 소개로 돌아가기
        </button>
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
              {analysisResult.report_form && <ReportForm reportText={analysisResult.report_form} />}
              <ResultDetails result={analysisResult} />
            </section>
          ) : (
            <section className="empty-result-panel">
              <h2>분석 결과가 여기에 표시됩니다</h2>
              <p>문서를 업로드하고 “문서 분석하기”를 누르면 신호등 판정과 신고서 초안을 확인할 수 있습니다.</p>
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
        이 서비스는 소비자에게 불리할 수 있는 문구를 쉽게 확인하기 위한 참고 도구입니다. 최종 판단이나 법적 조치는 관계 기관 상담을 통해 확인해주세요.
      </footer>
    </div>
  );
}

function LandingPage({ onStart }) {
  return (
    <div className="landing-shell">
      <nav className="landing-nav" aria-label="서비스 안내">
        <strong>찰칵! 소비자 공정 Guard</strong>
        <button type="button" onClick={onStart}>
          분석 시작
        </button>
      </nav>

      <main>
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <span className="landing-badge">AI 기반 불공정 문구 점검</span>
            <h1>복잡한 약관과 광고 문구, 신호등처럼 쉽게 확인하세요</h1>
            <p>
              문서를 올리면 AI가 소비자에게 불리할 수 있는 표현을 찾아 안전·주의·위험으로 안내하고, 필요한 경우 신고서 초안까지 정리해드립니다.
            </p>
            <div className="landing-actions">
              <button type="button" className="landing-primary" onClick={onStart}>
                문서 분석 시작하기
              </button>
              <a href="#how-it-works" className="landing-secondary">
                이용 방법 보기
              </a>
            </div>
          </div>

          <div className="signal-preview" aria-label="신호등 판정 미리보기">
            <div className="preview-card preview-safe">
              <span />
              <strong>안전</strong>
              <small>큰 위험 문구 없음</small>
            </div>
            <div className="preview-card preview-warning">
              <span />
              <strong>주의</strong>
              <small>확인 필요한 조건</small>
            </div>
            <div className="preview-card preview-danger">
              <span />
              <strong>위험</strong>
              <small>불리한 조항 가능성</small>
            </div>
          </div>
        </section>

        <section className="feature-band" aria-label="서비스 핵심 기능">
          <div className="feature-card feature-wide">
            <span className="feature-icon">AI</span>
            <h2>한눈에 보는 위험 판정</h2>
            <p>법률 용어를 몰라도 결과를 바로 이해할 수 있도록 핵심 문구와 쉬운 설명을 함께 보여줍니다.</p>
          </div>
          <div className="feature-card">
            <span className="feature-icon safe-dot">●</span>
            <h2>신호등 색상 체계</h2>
            <p>안전은 초록, 주의는 노랑, 위험은 빨강으로 현재 상태를 명확하게 구분합니다.</p>
          </div>
          <div className="feature-card">
            <span className="feature-icon">문서</span>
            <h2>신고서 초안 지원</h2>
            <p>위험한 문구가 발견되면 관계 기관 제출에 참고할 수 있는 초안을 이어서 확인할 수 있습니다.</p>
          </div>
        </section>

        <section className="process-band" id="how-it-works">
          <div className="landing-section-heading">
            <p className="eyebrow">Process</p>
            <h2>이렇게 사용해요</h2>
          </div>
          <ol className="process-list">
            <li>
              <span>1</span>
              <strong>문서 업로드</strong>
              <p>약관, 계약서, 광고 캡처를 PDF·JPG·PNG로 올립니다.</p>
            </li>
            <li>
              <span>2</span>
              <strong>AI 분석</strong>
              <p>문서 속 위험 문구와 관련 사례를 검토합니다.</p>
            </li>
            <li>
              <span>3</span>
              <strong>신호등 판정</strong>
              <p>안전·주의·위험으로 결과를 빠르게 확인합니다.</p>
            </li>
            <li>
              <span>4</span>
              <strong>다음 조치</strong>
              <p>신고서 초안과 상담 도우미로 후속 대응을 준비합니다.</p>
            </li>
          </ol>
        </section>

        <section className="landing-cta">
          <h2>지금 바로 내 문서를 점검해볼까요?</h2>
          <p>복잡한 조건은 AI에게 맡기고, 결과는 신호등처럼 편하게 확인하세요.</p>
          <button type="button" onClick={onStart}>
            분석 화면으로 이동
          </button>
        </section>
      </main>
    </div>
  );
}

function ResultDetails({ result }) {
  return (
    <section className="result-details" aria-label="참고 사례">
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
