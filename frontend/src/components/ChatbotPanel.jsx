import React, { useEffect, useMemo, useRef, useState } from "react";
import { sendChatMessage } from "../api/chatClient.js";
import SuggestedQuestionChips from "./SuggestedQuestionChips.jsx";

const BEFORE_ANALYSIS_QUESTIONS = ["무엇을 넣으면 되나요?", "광고 캡처 분석 가능?", "개인정보 저장되나요?", "분석 기준은 뭔가요?"];

const AFTER_ANALYSIS_QUESTIONS = [
  "왜 이런 판정인가요?",
  "문제 문구만 다시 보여줘",
  "소비자가 할 수 있는 조치는?",
  "신고서 초안 작성해줘",
  "관련 기관 알려줘",
];

function ChatbotPanel({
  analysisResult,
  externalQuestion,
  onExternalQuestionHandled,
  messages: controlledMessages,
  onMessagesChange,
  variant = "panel",
  onClose,
}) {
  const [localMessages, setLocalMessages] = useState([
    {
      role: "assistant",
      text: "안녕하세요. 문서 분석 전에는 업로드 방법을, 분석 후에는 결과 해석과 다음 조치를 도와드릴게요.",
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const handledExternalQuestionIdRef = useRef(null);
  const messages = controlledMessages || localMessages;
  const setMessages = onMessagesChange || setLocalMessages;

  const suggestedQuestions = useMemo(
    () => (analysisResult ? AFTER_ANALYSIS_QUESTIONS : BEFORE_ANALYSIS_QUESTIONS),
    [analysisResult],
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    if (externalQuestion) {
      const questionText = typeof externalQuestion === "string" ? externalQuestion : externalQuestion.text;
      const questionId = typeof externalQuestion === "string" ? questionText : externalQuestion.id;
      if (questionId && handledExternalQuestionIdRef.current === questionId) {
        return;
      }
      handledExternalQuestionIdRef.current = questionId;
      handleAsk(questionText);
      onExternalQuestionHandled?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalQuestion]);

  const handleSubmit = (event) => {
    event.preventDefault();
    const question = inputValue.trim();
    if (!question) {
      return;
    }
    setInputValue("");
    handleAsk(question);
  };

  const handleAsk = async (question) => {
    const pendingId = `pending-${Date.now()}`;
    const currentMessages = [...messages, { role: "user", text: question }];
    setMessages((current) => [
      ...current,
      { role: "user", text: question },
      { id: pendingId, role: "assistant", text: "답변 중입니다...", isPending: true },
    ]);
    setIsLoading(true);

    const answer = await sendChatMessage(question, currentMessages, analysisResult);
    setMessages((current) =>
      current.map((message) =>
        message.id === pendingId ? { role: "assistant", text: answer } : message,
      ),
    );
    setIsLoading(false);
  };

  return (
    <section className={`chatbot-panel ${variant}`} aria-label="분석 결과 도우미">
      <div className="chatbot-header">
        <div>
          <h2>분석 결과 도우미</h2>
        </div>
        {onClose && (
          <button type="button" className="icon-close" aria-label="챗봇 닫기" onClick={onClose}>
            x
          </button>
        )}
      </div>

      <div className="chat-messages" aria-live="polite">
        {messages.map((message, index) => (
          <div key={message.id || `${message.role}-${index}`} className={`chat-message ${message.role} ${message.isPending ? "is-loading" : ""}`}>
            <p>{formatChatText(message.text)}</p>
          </div>
        ))}
        {false && (
          <div className="chat-message assistant is-loading">
            <p>답변을 정리하는 중입니다...</p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <SuggestedQuestionChips questions={suggestedQuestions} onSelect={handleAsk} disabled={isLoading} />

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="궁금한 점을 입력하세요"
          aria-label="챗봇 질문 입력"
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !inputValue.trim()}>
          보내기
        </button>
      </form>
    </section>
  );
}

function formatChatText(text) {
  const normalizedText = String(text || "").trim();
  if (!normalizedText || normalizedText.includes("\n")) {
    return normalizedText;
  }

  return normalizedText
    .replace(/([.!?])\s+(?=[가-힣A-Z0-9])/g, "$1\n")
    .replace(/(다\.|요\.|니다\.)\s+(?=[가-힣A-Z0-9])/g, "$1\n")
    .replace(/\s+(-\s)/g, "\n$1")
    .replace(/\s+(\d+\.\s)/g, "\n$1");
}

export default ChatbotPanel;
