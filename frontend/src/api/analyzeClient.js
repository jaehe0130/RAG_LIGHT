const ANALYZE_API_URL = "/api/analyze";
const DEFAULT_INPUT_TYPE = "terms";

export async function analyzeDocument({ file, textInput }) {
  const formData = new FormData();
  formData.append("input_type", DEFAULT_INPUT_TYPE);
  if (file) {
    formData.append("file", file);
  }
  if (textInput?.trim()) {
    formData.append("text", textInput.trim());
  }

  const response = await fetch(ANALYZE_API_URL, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`문서 분석 요청에 실패했습니다. 상태 코드: ${response.status}`);
  }

  return response.json();
}
