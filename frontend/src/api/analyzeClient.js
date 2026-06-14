const ANALYZE_API_URL = "http://127.0.0.1:8000/api/analyze";

export async function analyzeDocument({ file, docType }) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("input_type", docType);

  const response = await fetch(ANALYZE_API_URL, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`문서 분석 요청에 실패했습니다. 상태 코드: ${response.status}`);
  }

  return response.json();
}
