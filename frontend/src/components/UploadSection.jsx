import React, { useRef, useState } from "react";

function UploadSection({ documentType, uploadedFile, onAnalyze }) {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(uploadedFile);
  const [docType, setDocType] = useState(documentType);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    const file = event.dataTransfer.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleSubmit = () => {
    onAnalyze({
      file: selectedFile,
      docType
    });
  };

  return (
    <section className="upload-panel" aria-label="문서 업로드">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Upload</p>
          <h2>이미지 업로드</h2>
        </div>
        <span className="file-state">{selectedFile ? "파일 선택됨" : "대기 중"}</span>
      </div>

      <div
        className={`drop-zone ${isDragging ? "is-dragging" : ""}`}
        onDragEnter={() => setIsDragging(true)}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          className="visually-hidden"
        />
        <strong>약관 이미지 또는 광고 캡처본</strong>
        <span>파일을 끌어오거나 버튼으로 선택하세요.</span>
        <button type="button" onClick={() => fileInputRef.current?.click()}>
          파일 선택
        </button>
      </div>

      <div className="form-row">
        <span className="field-label">문서 타입</span>
        <div className="segmented-control" role="radiogroup" aria-label="문서 타입">
          <label className={docType === "terms" ? "is-selected" : ""}>
            <input
              type="radio"
              name="docType"
              value="terms"
              checked={docType === "terms"}
              onChange={() => setDocType("terms")}
            />
            약관
          </label>
          <label className={docType === "ad" ? "is-selected" : ""}>
            <input
              type="radio"
              name="docType"
              value="ad"
              checked={docType === "ad"}
              onChange={() => setDocType("ad")}
            />
            광고
          </label>
        </div>
      </div>

      <div className="file-name">
        <span>업로드 파일명</span>
        <strong>{selectedFile?.name || "선택된 파일 없음"}</strong>
      </div>

      <button type="button" className="primary-action" onClick={handleSubmit}>
        Mock 분석 실행
      </button>
    </section>
  );
}

export default UploadSection;
