import React, { useEffect, useRef, useState } from "react";

const DOC_TYPE_LABELS = {
  terms: "약관",
  ad: "광고"
};

const ACCEPTED_FILE_TYPES = "image/*,.pdf,application/pdf";

function UploadSection({ documentType, uploadedFiles = [], isAnalyzing, analysisStep, onAnalyze }) {
  const fileInputRef = useRef(null);
  const [selectedFiles, setSelectedFiles] = useState(uploadedFiles);
  const [docType, setDocType] = useState(documentType);
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [fileError, setFileError] = useState("");

  const firstFile = selectedFiles[0];
  const firstFileIsImage = firstFile?.type?.startsWith("image/") || false;
  const firstFileIsPdf = firstFile?.type === "application/pdf" || firstFile?.name?.toLowerCase().endsWith(".pdf") || false;

  useEffect(() => {
    if (!firstFile || !firstFileIsImage || fileError) {
      setPreviewUrl("");
      return undefined;
    }

    const nextPreviewUrl = URL.createObjectURL(firstFile);
    setPreviewUrl(nextPreviewUrl);

    return () => URL.revokeObjectURL(nextPreviewUrl);
  }, [firstFile, firstFileIsImage, fileError]);

  // 파일 선택과 드래그 앤 드롭에서 같은 검증 로직을 사용한다.
  const selectFiles = (fileList) => {
    const nextFiles = Array.from(fileList || []);
    if (nextFiles.length === 0) {
      return;
    }

    const invalidFile = nextFiles.find((file) => !isAllowedFile(file));
    if (invalidFile) {
      setSelectedFiles([]);
      setFileError("PDF 또는 이미지 파일만 업로드할 수 있습니다. JPG, PNG, PDF 파일을 선택해 주세요.");
      return;
    }

    setSelectedFiles(nextFiles);
    setFileError("");
  };

  const handleFileChange = (event) => {
    selectFiles(event.target.files);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    selectFiles(event.dataTransfer.files);
  };

  const handleSubmit = () => {
    onAnalyze({
      files: selectedFiles,
      docType
    });
  };

  return (
    <section className="upload-panel" aria-label="문서 업로드">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Upload</p>
          <h2>문서 업로드</h2>
        </div>
        <span className={`file-state ${selectedFiles.length > 0 ? "ready" : ""}`}>
          {selectedFiles.length > 0 ? `${selectedFiles.length}개 선택됨` : "파일 필요"}
        </span>
      </div>

      <div
        className={`drop-zone ${isDragging ? "is-dragging" : ""} ${selectedFiles.length > 0 ? "has-preview" : ""}`}
        onDragEnter={() => setIsDragging(true)}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_FILE_TYPES}
          multiple
          onChange={handleFileChange}
          className="visually-hidden"
        />

        {previewUrl ? (
          <div className="preview-frame">
            <img src={previewUrl} alt="업로드한 이미지 미리보기" />
          </div>
        ) : firstFileIsPdf ? (
          <div className="pdf-preview">
            <strong>PDF</strong>
            <span>{firstFile.name}</span>
          </div>
        ) : (
          <div className="drop-copy">
            <span className="upload-icon" aria-hidden="true">
              +
            </span>
            <strong>PDF, JPG, PNG 파일을 끌어오세요</strong>
            <span>여러 파일을 한 번에 선택할 수 있습니다.</span>
          </div>
        )}

        <button type="button" className="secondary-action" onClick={() => fileInputRef.current?.click()}>
          파일 선택
        </button>
      </div>

      {fileError && <p className="file-error">{fileError}</p>}

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

      <div className="upload-meta">
        <div>
          <span>파일 수</span>
          <strong>{selectedFiles.length > 0 ? `${selectedFiles.length}개` : "선택된 파일 없음"}</strong>
        </div>
        <div>
          <span>문서 타입</span>
          <strong>{DOC_TYPE_LABELS[docType]}</strong>
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <ul className="file-list" aria-label="선택된 파일 목록">
          {selectedFiles.map((file) => (
            <li key={`${file.name}-${file.size}`}>
              <span>{getFileBadge(file)}</span>
              <strong>{file.name}</strong>
            </li>
          ))}
        </ul>
      )}

      {isAnalyzing && (
        <div className="inline-loading" aria-live="polite">
          <div className="loading-bar">
            <span />
          </div>
          <p>{analysisStep || "OCR로 문서를 읽는 중입니다"}</p>
        </div>
      )}

      <button
        type="button"
        className="primary-action"
        disabled={selectedFiles.length === 0 || Boolean(fileError) || isAnalyzing}
        onClick={handleSubmit}
      >
        {isAnalyzing ? "분석 중" : "분석 시작"}
      </button>
    </section>
  );
}

function isAllowedFile(file) {
  return file.type.startsWith("image/") || file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function getFileBadge(file) {
  if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
    return "PDF";
  }

  return "IMG";
}

export default UploadSection;
