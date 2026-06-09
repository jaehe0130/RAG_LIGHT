import React, { useState } from "react";

function ReportForm({ reportText }) {
  const [copyState, setCopyState] = useState("idle");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(reportText);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      setCopyState("failed");
    }
  };

  const handlePdfDownload = () => {
    const pdfBlob = createReportPdf(reportText);
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
          <p className="eyebrow">Report</p>
          <h2>신고서 초안</h2>
        </div>
        <span className="danger-chip">문서 초안</span>
      </div>

      <textarea readOnly value={reportText} aria-label="신고서 초안 내용" />

      <div className="button-row">
        <button type="button" onClick={handleCopy}>
          문서 복사하기
        </button>
        <button type="button" className="secondary-action" onClick={handlePdfDownload}>
          PDF 다운로드
        </button>
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
    `<< /Length ${drawCommand.length} >>\nstream\n${drawCommand}\nendstream`
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
