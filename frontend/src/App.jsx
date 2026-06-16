import React, { useEffect, useState } from "react";
import { analyzeDocument } from "./api/analyzeClient.js";
import AnalysisProgress from "./components/AnalysisProgress.jsx";
import ChatbotPanel from "./components/ChatbotPanel.jsx";
import ReportForm from "./components/ReportForm.jsx";
import RiskResultCard from "./components/RiskResultCard.jsx";
import UploadPanel from "./components/UploadPanel.jsx";

const PROGRESS_STEP_COUNT = 5;
const INITIAL_CHAT_MESSAGES = [
  {
    role: "assistant",
    text: "안녕하세요. 문서 분석 전에는 업로드 방법을, 분석 후에는 결과 해석과 다음 조치를 도와드릴게요.",
  },
];
const STORAGE_KEYS = {
  analysisResult: "rag-light-analysis-result",
  chatMessages: "rag-light-chat-messages",
  textInput: "rag-light-text-input",
};

function readStoredJson(key, fallback) {
  try {
    const value = window.sessionStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function App() {
  const [view, setView] = useState("landing");
  const [selectedFile, setSelectedFile] = useState(null);
  const [textInput, setTextInput] = useState(() => window.sessionStorage.getItem(STORAGE_KEYS.textInput) || "");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progressIndex, setProgressIndex] = useState(() => (window.sessionStorage.getItem(STORAGE_KEYS.textInput) ? 1 : 0));
  const [analysisResult, setAnalysisResult] = useState(() => readStoredJson(STORAGE_KEYS.analysisResult, null));
  const [errorMessage, setErrorMessage] = useState("");
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatMessages, setChatMessages] = useState(() => readStoredJson(STORAGE_KEYS.chatMessages, INITIAL_CHAT_MESSAGES));
  const [isChatOpen, setIsChatOpen] = useState(false);

  useEffect(() => {
    window.sessionStorage.setItem(STORAGE_KEYS.textInput, textInput);
  }, [textInput]);

  useEffect(() => {
    if (analysisResult) {
      window.sessionStorage.setItem(STORAGE_KEYS.analysisResult, JSON.stringify(analysisResult));
      return;
    }
    window.sessionStorage.removeItem(STORAGE_KEYS.analysisResult);
  }, [analysisResult]);

  useEffect(() => {
    window.sessionStorage.setItem(STORAGE_KEYS.chatMessages, JSON.stringify(chatMessages));
  }, [chatMessages]);

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
    if ((!selectedFile && !textInput.trim()) || isAnalyzing) {
      return;
    }

    setIsAnalyzing(true);
    setProgressIndex(1);
    setErrorMessage("");
    setAnalysisResult(null);

    try {
      const apiResult = await analyzeDocument({ file: selectedFile, textInput });
      const viewModel = mapApiResultToViewModel(apiResult, selectedFile);

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

  const isInitialChatState = (messages) =>
    messages.length === INITIAL_CHAT_MESSAGES.length &&
    messages.every((message, index) => message.role === INITIAL_CHAT_MESSAGES[index]?.role && message.text === INITIAL_CHAT_MESSAGES[index]?.text);

  const resetAnalysisSession = () => {
    setAnalysisResult(null);
    setChatQuestion("");
    setChatMessages(INITIAL_CHAT_MESSAGES);
    window.sessionStorage.removeItem(STORAGE_KEYS.analysisResult);
    window.sessionStorage.removeItem(STORAGE_KEYS.chatMessages);
  };

  if (view === "landing") {
    return <LandingPage onStart={() => setView("analysis")} />;
  }

  return (
    <div className="app-shell analysis-shell">
      <header className="hero-header analysis-header">
        <div>
          <h1>소비자에게 불리할 수 있는 문구를 쉽고 정확하게 확인하세요</h1>
          <p>파일 업로드나 직접 입력으로 위험 문구를 찾아 신호등 판정과 다음 조치를 안내합니다.</p>
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
              textInput={textInput}
              isAnalyzing={isAnalyzing}
              errorMessage={errorMessage}
              onFileChange={(file) => {
                if (file !== selectedFile && (analysisResult || !isInitialChatState(chatMessages) || chatQuestion)) {
                  resetAnalysisSession();
                }
                setSelectedFile(file);
                setProgressIndex(file || textInput.trim() ? 1 : 0);
                setErrorMessage("");
              }}
              onTextChange={(value) => {
                if (value !== textInput && (analysisResult || !isInitialChatState(chatMessages) || chatQuestion)) {
                  resetAnalysisSession();
                }
                setTextInput(value);
                setProgressIndex(selectedFile || value.trim() ? 1 : 0);
                setErrorMessage("");
              }}
              onResetAll={() => {
                setSelectedFile(null);
                setTextInput("");
                setProgressIndex(0);
                setErrorMessage("");
                setAnalysisResult(null);
                setChatQuestion("");
                setChatMessages(INITIAL_CHAT_MESSAGES);
                window.sessionStorage.removeItem(STORAGE_KEYS.textInput);
                window.sessionStorage.removeItem(STORAGE_KEYS.analysisResult);
                window.sessionStorage.removeItem(STORAGE_KEYS.chatMessages);
              }}
              onAnalyze={handleAnalyze}
            />

            <AnalysisProgress currentStepIndex={progressIndex} isAnalyzing={isAnalyzing} hasFile={Boolean(selectedFile || textInput.trim())} />
          </section>

          {analysisResult ? (
            <section className="results-area" aria-label="분석 결과">
              <RiskResultCard result={analysisResult} onAskQuestion={askChatbot} />
              {isSafeResult(analysisResult) ? (
                <SafeResultGuide />
              ) : isWarningResult(analysisResult) ? (
                <>
                  <WarningResultGuide />
                  {analysisResult.report_form && <WarningReviewMemo reportText={analysisResult.report_form} result={analysisResult} />}
                  <WarningResultDetails result={analysisResult} />
                </>
              ) : (
                <>
                  {analysisResult.report_form && <ReportForm reportText={analysisResult.report_form} result={analysisResult} />}
                  <ResultDetails result={analysisResult} />
                </>
              )}
            </section>
          ) : (
            <section className="empty-result-panel">
              <h2>분석 결과가 여기에 표시됩니다</h2>
              <p>문서를 업로드하거나 텍스트를 입력한 뒤 “문서 분석하기”를 누르면 신호등 판정과 신고서 초안을 확인할 수 있습니다.</p>
            </section>
          )}
        </div>

        <aside className="chat-side">
          <ChatbotPanel
            analysisResult={analysisResult}
            externalQuestion={!isChatOpen ? chatQuestion : ""}
            onExternalQuestionHandled={() => setChatQuestion("")}
            messages={chatMessages}
            onMessagesChange={setChatMessages}
          />
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
            messages={chatMessages}
            onMessagesChange={setChatMessages}
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

      <main>
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <span className="landing-badge">AI 기반 불공정 문구 점검</span>
            <h1>복잡한 약관과 광고 문구, 신호등처럼 쉽게 확인하세요</h1>
            <div className="landing-hero-summary">
              <p>
                파일을 올리거나 문구를 붙여넣으면 AI가 소비자에게 불리할 수 있는 표현을 찾아드립니다.
              </p>
              <ul>
                <li>안전·주의·위험 신호등으로 결과를 한눈에 확인</li>
                <li>위험 문구와 이유를 쉬운 말로 정리</li>
                <li>필요한 경우 신고서 초안까지 준비</li>
              </ul>
            </div>
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
            <h2>이렇게 사용해요</h2>
          </div>
          <ol className="process-list">
            <li>
              <span>1</span>
              <strong>문서 업로드 또는 직접 입력</strong>
              <p>약관, 계약서, 광고 캡처를 파일로 올리거나 텍스트로 붙여넣습니다.</p>
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
        <section className="form-preview-band" id="form-previews">
          <div className="landing-section-heading">
            <h2>지원 양식 미리보기 및 다운로드</h2>
            <p>RAG Light가 자동 완성을 지원하는 공식 양식들입니다. 직접 다운로드하여 제출하실 수도 있습니다.</p>
          </div>
          <div className="form-preview-grid">
            <a href="/forms/form5.pdf" download="불공정거래행위_신고서.pdf" className="form-preview-card">
              <span className="form-icon">📄</span>
              <strong>불공정거래행위 신고서</strong>
              <small>양식 다운로드 (PDF)</small>
            </a>
            <a href="/forms/form6.pdf" download="표시광고법_위반_신고서.pdf" className="form-preview-card">
              <span className="form-icon">📄</span>
              <strong>표시·광고법 위반 신고서</strong>
              <small>양식 다운로드 (PDF)</small>
            </a>
            <a href="/forms/form7.pdf" download="방문판매법_위반_신고서.pdf" className="form-preview-card">
              <span className="form-icon">📄</span>
              <strong>방문판매법 위반 신고서</strong>
              <small>양식 다운로드 (PDF)</small>
            </a>
            <a href="/forms/form10.pdf" download="할부거래법_위반_신고서.pdf" className="form-preview-card">
              <span className="form-icon">📄</span>
              <strong>할부거래법 위반 신고서</strong>
              <small>양식 다운로드 (PDF)</small>
            </a>
            <a href="/forms/form8.pdf" download="불공정약관_심사청구서.pdf" className="form-preview-card">
              <span className="form-icon">📄</span>
              <strong>불공정약관 심사 청구서</strong>
              <small>양식 다운로드 (PDF)</small>
            </a>
            <a href="/forms/form9.pdf" download="전자상거래법_위반_신고서.pdf" className="form-preview-card">
              <span className="form-icon">📄</span>
              <strong>전자상거래법 위반 신고서</strong>
              <small>양식 다운로드 (PDF)</small>
            </a>
          </div>
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

function ResultDetails({ result, tone = "danger" }) {
  const isWarning = tone === "warning";

  return (
    <section className="result-details" aria-label="참고 사례">
      <div className="detail-card">
        <h2>관련 사례 기반 설명</h2>
        {result.reference_cases.length > 0 ? (
          <ul className="case-list">
            {result.reference_cases.slice(0, 3).map((caseText, index) => (
              <li key={`${index}-${caseText.slice(0, 24)}`}>
                <span>사례 {index + 1}</span>
                <p className="case-summary">관련 사례 전문은 아래에서 펼쳐 확인할 수 있습니다.</p>
                <details className="case-detail">
                  <summary>사례 내용 보기</summary>
                  <p>{caseText}</p>
                </details>
              </li>
            ))}
          </ul>
        ) : (
          <p>아직 표시할 관련 사례가 없습니다.</p>
        )}
      </div>
    </section>
  );
}

function WarningResultGuide() {
  return (
    <section className="warning-result-guide" aria-label="주의 판정 다음 조치">
      <div>
        <h2>바로 신고하기 전에 한 번 더 확인해보면 좋아요</h2>
        <p>
          주의 판정은 위험 가능성이 있는 표현이 발견됐다는 의미입니다. 먼저 문제 문구를 확인하고, 사업자에게 조건을 명확히 물어본 뒤 필요하면 신고 자료로 정리하세요.
        </p>
      </div>
      <ul>
        <li>환불, 해지, 위약금, 효과 보장처럼 실제 피해로 이어질 수 있는 문구를 우선 확인하세요.</li>
        <li>아직 피해가 발생하지 않았다면 신고서 대신 검토 메모로 보관하는 편이 부담이 적습니다.</li>
        <li>같은 조건으로 결제했거나 거절당한 기록이 있으면 캡처와 영수증을 함께 모아두세요.</li>
      </ul>
    </section>
  );
}

function WarningReviewMemo({ reportText, result }) {
  const [copyState, setCopyState] = useState("idle");
  const [memoText, setMemoText] = useState("");
  const forms = result.recommended_forms || [];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(memoText);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      setCopyState("failed");
    }
  };

  return (
    <section className="result-panel warning-review-memo" aria-label="주의 판정 검토 메모">
      <div className="panel-heading">
        <div>
          <h2>검토 메모</h2>
          <p>신고서로 바로 제출하기보다, 주의 문구와 확인할 내용을 보관하는 용도입니다.</p>
        </div>
      </div>

      <textarea
        value={memoText}
        onChange={(event) => setMemoText(event.target.value)}
        placeholder="확인할 문구, 사업자에게 물어볼 내용, 결제/환불/해지 조건 등을 자유롭게 적어보세요."
        aria-label="주의 판정 검토 메모 내용"
      />

      <div className="button-row">
        <button type="button" onClick={handleCopy}>
          메모 복사하기
        </button>
      </div>

      {forms.length > 0 && (
        <section className="recommended-form-section" aria-label="필요 시 참고할 신고 양식">
          <div className="recommended-form-heading">
            <h3>필요 시 참고할 신고 양식</h3>
            <p>문구를 다시 확인한 뒤 실제 피해나 거절 기록이 있을 때 참고할 수 있는 양식입니다.</p>
          </div>
          <div className="recommended-form-grid">
            {forms.slice(0, 2).map((form) => (
              <article key={`${form.title}-${form.file}`} className="recommended-form-card">
                <div>
                  <h4>{form.title}</h4>
                  {form.reason && <strong>{form.reason}</strong>}
                  <p>{form.description}</p>
                </div>
                <div className="recommended-form-actions">
                  <a href={form.file} target="_blank" rel="noreferrer" className="preview-action">
                    미리보기
                  </a>
                  <a href={form.file} download>
                    다운로드
                  </a>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {copyState === "copied" && <p className="feedback success">메모를 복사했습니다.</p>}
      {copyState === "failed" && <p className="feedback">클립보드 복사에 실패했습니다.</p>}
    </section>
  );
}

function WarningResultDetails({ result }) {
  return (
    <section className="result-details" aria-label="주의 판정 참고 사례">
      <div className="detail-card">
        <h2>비슷한 사례 참고</h2>
        <p className="case-helper">바로 신고하기보다, 어떤 유형의 사례와 가까운지 참고해서 문구를 다시 확인해보세요.</p>
        {result.reference_cases.length > 0 ? (
          <ul className="case-list">
            {result.reference_cases.slice(0, 2).map((caseText, index) => (
              <li key={`${index}-${caseText.slice(0, 24)}`}>
                <span>참고 {index + 1}</span>
                <p className="case-summary">유사 사례 전문은 아래에서 펼쳐 확인할 수 있습니다.</p>
                <details className="case-detail">
                  <summary>내용 펼쳐보기</summary>
                  <p>{caseText}</p>
                </details>
              </li>
            ))}
          </ul>
        ) : (
          <p>아직 표시할 유사 사례가 없습니다.</p>
        )}
      </div>
    </section>
  );
}

function SafeResultGuide() {
  return (
    <section className="safe-result-guide" aria-label="안전 판정 다음 조치">
      <div>
        <h2>신고 준비가 필요하지 않은 상태로 보여요</h2>
        <p>
          현재 분석에서는 뚜렷한 위험 문구가 확인되지 않았습니다. 신고 양식 대신 문서를 보관하고, 계약 전 최종 조건만 다시 확인해보세요.
        </p>
      </div>
      <ul>
        <li>결제 금액, 환불 조건, 해지 방법처럼 실제 이용에 영향을 주는 항목을 한 번 더 확인하세요.</li>
        <li>추가 문구나 새 광고 이미지가 생기면 다시 분석해 비교해볼 수 있습니다.</li>
        <li>불안한 표현이 있다면 챗봇에 해당 문장을 붙여 넣고 의미를 물어보세요.</li>
      </ul>
    </section>
  );
}

function mapApiResultToViewModel(apiResult, file) {
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
    inputType: apiResult.input_type || "",
    violationType: analysis.violation_type || "",
    recommended_forms: analysis.recommended_forms || [],
    fileName: file?.name || "",
  };
}

function isSafeResult(result) {
  return normalizeSignal(result?.signal) === "GREEN";
}

function isWarningResult(result) {
  return normalizeSignal(result?.signal) === "YELLOW";
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
