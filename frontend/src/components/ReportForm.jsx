import React, { useEffect, useState } from "react";

const REPORT_LINKS = [
  {
    label: "공정위에 신고하기",
    href: "https://www.ftc.go.kr/www/index.do",
  },
  {
    label: "국민신문고로 접수하기",
    href: "https://www.epeople.go.kr/index.jsp",
  },
];

const DEFAULT_RECOMMENDED_FORMS = [
  {
    title: "공정거래위원회 신고서",
    description: "추천 양식 정보가 아직 응답에 없을 때 사용할 수 있는 기본 신고 양식입니다.",
    file: "/forms/form5.pdf",
    reason: "백엔드 추천 양식이 없어서 기본 신고 양식을 표시합니다.",
  },
  {
    title: "불공정약관 심사청구서",
    description: "환불 불가, 과도한 위약금, 계약 해지 제한 등 약관 문제가 의심될 때 참고하세요.",
    file: "/forms/form8.pdf",
    reason: "약관·계약서 분석에서 가장 자주 연결되는 양식입니다.",
  },
];

function ReportForm({ reportText, result }) {
  const [copyState, setCopyState] = useState("idle");
  const [editableReportText, setEditableReportText] = useState(reportText || "");
  const recommendedForms = result?.recommended_forms?.length ? result.recommended_forms : DEFAULT_RECOMMENDED_FORMS;

  useEffect(() => {
    setEditableReportText(reportText || "");
  }, [reportText]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(editableReportText);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      setCopyState("failed");
    }
  };

  const handlePdfDownload = () => {
    const pdfBlob = createReportPdf(editableReportText);
    const url = URL.createObjectURL(pdfBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "report-draft.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="result-panel report-panel" aria-label="신고서 초안">
      <div className="panel-heading">
        <div>
          <h2>신고서 초안</h2>
        </div>
      </div>

      <div className="report-ready-steps" aria-label="신고 준비 체크">
        <div>
          <span>1</span>
          <strong>문제 문구 확인</strong>
          <p>위험하다고 표시된 표현을 먼저 확인하세요.</p>
        </div>
        <div>
          <span>2</span>
          <strong>자료 보관</strong>
          <p>계약서, 광고 화면, 결제 기록을 함께 모아두세요.</p>
        </div>
        <div>
          <span>3</span>
          <strong>초안 활용</strong>
          <p>아래 내용을 복사해 필요한 부분만 보완하세요.</p>
        </div>
      </div>

      <label className="report-editor-label" htmlFor="report-draft-editor">
        초안 내용을 선택해서 직접 수정할 수 있습니다.
      </label>
      <textarea
        id="report-draft-editor"
        value={editableReportText}
        onChange={(event) => setEditableReportText(event.target.value)}
        aria-label="수정 가능한 신고서 초안 내용"
        spellCheck="false"
      />

      <div className="button-row">
        <button type="button" onClick={handleCopy}>
          문서 복사하기
        </button>
        <button type="button" className="secondary-action" onClick={handlePdfDownload}>
          PDF 다운로드
        </button>
      </div>

      <section className="recommended-form-section" aria-label="추천 신고 양식">
        <div className="recommended-form-heading">
          <h3>추천 신고 양식</h3>
          <p>아래 양식을 열어 내용을 확인한 뒤 필요한 항목을 채워 제출할 수 있습니다.</p>
        </div>
        <div className="recommended-form-grid">
          {recommendedForms.map((form) => (
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

      <div className="report-link-box" aria-label="신고서 제출 홈페이지 바로가기">
        <span>신고서 제출 바로가기</span>
        <div className="report-link-actions">
          {REPORT_LINKS.map((link) => (
            <a key={link.href} href={link.href} target="_blank" rel="noreferrer">
              {link.label}
            </a>
          ))}
        </div>
      </div>

      {copyState === "copied" && <p className="feedback success">복사되었습니다.</p>}
      {copyState === "failed" && <p className="feedback">클립보드 복사에 실패했습니다.</p>}
    </section>
  );
}

function createReportPdf(reportText) {
  const pageWidth = 595;
  const pageHeight = 842;
  const canvasScale = 2;
  const canvas = document.createElement("canvas");
  canvas.width = pageWidth * canvasScale;
  canvas.height = pageHeight * canvasScale;

  const context = canvas.getContext("2d");
  context.scale(canvasScale, canvasScale);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, pageWidth, pageHeight);

  context.fillStyle = "#1f2933";
  context.font = '700 22px "Malgun Gothic", "Apple SD Gothic Neo", sans-serif';
  context.fillText("신고서 초안", 48, 58);

  context.font = '15px "Malgun Gothic", "Apple SD Gothic Neo", sans-serif';
  context.fillStyle = "#263747";
  drawWrappedText(context, reportText, 48, 96, pageWidth - 96, 25);

  const imageData = canvas.toDataURL("image/jpeg", 0.92);
  const imageBinary = atob(imageData.split(",")[1]);
  const pdfBinary = buildSingleImagePdf(imageBinary, pageWidth, pageHeight);

  return new Blob([binaryStringToUint8Array(pdfBinary)], { type: "application/pdf" });
}

function drawWrappedText(context, text, x, y, maxWidth, lineHeight) {
  const paragraphs = text.split("\n");
  let currentY = y;

  paragraphs.forEach((paragraph) => {
    if (!paragraph) {
      currentY += lineHeight;
      return;
    }

    const words = paragraph.split(" ");
    let line = "";

    words.forEach((word) => {
      const testLine = line ? `${line} ${word}` : word;
      if (context.measureText(testLine).width > maxWidth && line) {
        context.fillText(line, x, currentY);
        currentY += lineHeight;
        line = word;
      } else {
        line = testLine;
      }
    });

    if (line) {
      context.fillText(line, x, currentY);
      currentY += lineHeight;
    }
  });
}

function buildSingleImagePdf(imageBinary, pageWidth, pageHeight) {
  const drawCommand = `q\n${pageWidth} 0 0 ${pageHeight} 0 0 cm\n/Im0 Do\nQ`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`,
    `<< /Type /XObject /Subtype /Image /Width ${pageWidth * 2} /Height ${pageHeight * 2} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${imageBinary.length} >>\nstream\n${imageBinary}\nendstream`,
    `<< /Length ${drawCommand.length} >>\nstream\n${drawCommand}\nendstream`,
  ];

  let pdf = "%PDF-1.4\n";
  const offsets = [0];

  objects.forEach((object, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });

  const xrefOffset = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += "0000000000 65535 f \n";
  offsets.slice(1).forEach((offset) => {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  });
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;

  return pdf;
}

function binaryStringToUint8Array(binaryString) {
  const bytes = new Uint8Array(binaryString.length);
  for (let index = 0; index < binaryString.length; index += 1) {
    bytes[index] = binaryString.charCodeAt(index);
  }
  return bytes;
}

export default ReportForm;
