const CHAT_API_URL = "/api/chat";

export async function sendChatMessage(question, history, analysisResult) {
  const payload = buildChatPayload(question, history, analysisResult);

  try {
    const response = await fetch(CHAT_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`챗봇 응답 실패: ${response.status}`);
    }

    const data = await response.json();
    return data.response || data.answer || data.message || "답변을 받았지만 표시할 내용이 없습니다.";
  } catch {
    // 백엔드 /api/chat 통신 실패 시 mock 답변 반환
    return buildMockAnswer(question, analysisResult);
  }
}

function buildChatPayload(question, history, analysisResult) {
  const formattedHistory = history.map(msg => ({
    role: msg.role,
    content: msg.text
  }));

  let contextStr = "";
  if (analysisResult) {
    contextStr = `[문서 위험도 판정]: ${analysisResult.signal_color || analysisResult.signal || '알 수 없음'}\n`;
    if (analysisResult.main_warning || analysisResult.summary) {
      contextStr += `[핵심 요약]: ${analysisResult.main_warning || analysisResult.summary}\n`;
    }
    if (analysisResult.toxic_clauses && analysisResult.toxic_clauses.length > 0) {
      contextStr += `[탐지된 독소 조항]: ${JSON.stringify(analysisResult.toxic_clauses)}\n`;
    }
    if (analysisResult.reference_cases && analysisResult.reference_cases.length > 0) {
      contextStr += `[참조 판례]: ${JSON.stringify(analysisResult.reference_cases)}\n`;
    }
    if (analysisResult.report_form && analysisResult.report_form.content) {
      contextStr += `[1차 신고서 초안]:\n${analysisResult.report_form.content}\n`;
    }
  }

  return {
    query: question,
    history: formattedHistory,
    context: contextStr
  };
}

function buildMockAnswer(question, analysisResult) {
  if (!analysisResult) {
    if (question.includes("업로드")) {
      return "PDF, JPG, PNG 형식의 약관, 광고 캡처, 계약서 이미지를 올릴 수 있습니다. 글자가 선명할수록 분석 결과가 좋아집니다.";
    }
    if (question.includes("광고")) {
      return "네. 광고 캡처 이미지도 분석할 수 있습니다. 과장 표현, 환불 조건, 제한 문구처럼 소비자가 놓치기 쉬운 내용을 확인합니다.";
    }
    if (question.includes("개인정보")) {
      return "현재 화면은 분석을 위해 파일을 백엔드로 전송합니다. 주민등록번호, 계좌번호 같은 민감정보는 가리고 업로드하는 것을 권장합니다.";
    }
    return "업로드한 문서에서 소비자에게 불리할 수 있는 문구를 찾고, 관련 사례와 비교해 쉬운 설명을 제공하는 방식입니다.";
  }

  const clauses = analysisResult.toxic_clauses || [];
  if (question.includes("왜")) {
    return `현재 판정은 "${analysisResult.riskLabel}"입니다. 특히 ${clauses.length > 0 ? clauses.join(", ") : "문서 속 주요 조건"} 부분이 소비자에게 불리하게 해석될 수 있어 주의가 필요합니다.`;
  }
  if (question.includes("문구")) {
    return clauses.length > 0 ? `문제 가능성이 있는 문구는 다음과 같습니다: ${clauses.join(", ")}` : "현재 결과에서 별도로 표시된 위험 문구는 없습니다.";
  }
  if (question.includes("조치")) {
    return "계약 전이라면 조건을 다시 확인하고, 이미 피해가 발생했다면 증빙 자료를 모아 한국소비자원 또는 공정거래위원회 상담을 받아보세요.";
  }
  if (question.includes("신고서")) {
    return analysisResult.report_form || "신고서 초안은 분석 결과가 충분할 때 생성됩니다. 핵심 문구와 피해 내용을 함께 정리해 주세요.";
  }
  if (question.includes("기관")) {
    return "소비자 피해 상담은 한국소비자원 1372 소비자상담센터, 표시·광고나 불공정거래 관련 내용은 공정거래위원회를 확인해 보세요.";
  }

  return "현재 분석 결과를 바탕으로 보면, 표시된 위험 문구를 먼저 확인하고 관련 자료를 저장해 두는 것이 좋습니다.";
}
