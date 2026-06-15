import React, { useRef, useState } from "react";

const ACCEPTED_FILE_TYPES = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

function UploadPanel({ selectedFile, isAnalyzing, errorMessage, onFileChange, onAnalyze }) {
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState("");

  const handleFiles = (fileList) => {
    const file = Array.from(fileList || [])[0];
    if (!file) {
      return;
    }

    if (!isAllowedFile(file)) {
      setLocalError("PDF, JPG, PNG 파일만 업로드할 수 있습니다.");
      onFileChange(null);
      return;
    }

    setLocalError("");
    onFileChange(file);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    handleFiles(event.dataTransfer.files);
  };

  return (
    <section className="upload-panel" aria-label="문서 업로드">
      <div className="section-heading">
        <h2>분석할 문서를 올려주세요</h2>
        <p>PDF, JPG, PNG 형식의 약관, 광고 캡처, 계약서 이미지를 지원합니다.</p>
      </div>

      <div
        className={`drop-zone ${isDragging ? "is-dragging" : ""} ${selectedFile ? "has-file" : ""}`}
        onDragEnter={() => setIsDragging(true)}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_FILE_TYPES}
          className="visually-hidden"
          onChange={(event) => handleFiles(event.target.files)}
        />

        <div className="drop-copy">
          <strong>{selectedFile ? selectedFile.name : "파일을 여기에 놓거나 선택하세요"}</strong>
          <span>{selectedFile ? getFileDescription(selectedFile) : "업로드 가능 형식: PDF, JPG, PNG"}</span>
        </div>

        <button type="button" className="secondary-action" onClick={() => fileInputRef.current?.click()} disabled={isAnalyzing}>
          파일 선택
        </button>
      </div>

      {(localError || errorMessage) && <p className="user-error">{localError || errorMessage}</p>}

      <button type="button" className="primary-action" disabled={!selectedFile || isAnalyzing || Boolean(localError)} onClick={onAnalyze}>
        {isAnalyzing ? "분석 중입니다" : "문서 분석하기"}
      </button>
    </section>
  );
}

function isAllowedFile(file) {
  const name = file.name.toLowerCase();
  return file.type === "application/pdf" || file.type === "image/jpeg" || file.type === "image/png" || /\.(pdf|jpe?g|png)$/.test(name);
}

function getFileDescription(file) {
  const sizeMb = file.size / 1024 / 1024;
  return `${file.type || "파일"} · ${sizeMb.toFixed(1)}MB`;
}

export default UploadPanel;
