import React, { useEffect, useRef, useState } from "react";

const DOC_TYPE_LABELS = {
  terms: "약관",
  ad: "광고"
};

function UploadSection({ documentType, uploadedFile, isAnalyzing, analysisStep, onAnalyze }) {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(uploadedFile);
  const [docType, setDocType] = useState(documentType);
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [fileError, setFileError] = useState("");

  useEffect(() => {
    if (!selectedFile || fileError) {
      setPreviewUrl("");
      return undefined;
    }

    const nextPreviewUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(nextPreviewUrl);

    return () => URL.revokeObjectURL(nextPreviewUrl);
  }, [selectedFile, fileError]);

  // 파일 검증은 업로드와 드래그 앤 드롭에서 같이 사용한다.
  const selectFile = (file) => {
    if (!file) {
      return;
    }

    if (!file.type.startsWith("image/")) {
      setSelectedFile(null);
      setFileError("이미지 파일만 업로드할 수 있습니다. PNG, JPG, JPEG 파일을 선택해 주세요.");
      return;
    }

    setSelectedFile(file);
    setFileError("");
  };

  const handleFileChange = (event) => {
    selectFile(event.target.files?.[0]);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    selectFile(event.dataTransfer.files?.[0]);
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
        <span className={`file-state ${selectedFile ? "ready" : ""}`}>
          {selectedFile ? "준비 완료" : "파일 필요"}
        </span>
      </div>

      <div
        className={`drop-zone ${isDragging ? "is-dragging" : ""} ${previewUrl ? "has-preview" : ""}`}
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

        {previewUrl ? (
          <div className="preview-frame">
            <img src={previewUrl} alt="업로드한 문서 미리보기" />
          </div>
        ) : (
          <div className="drop-copy">
            <span className="upload-icon" aria-hidden="true">
              +
            </span>
            <strong>약관 이미지 또는 광고 캡처본을 끌어오세요</strong>
            <span>이미지를 선택하면 이곳에 미리보기가 표시됩니다.</span>
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
          <span>파일명</span>
          <strong>{selectedFile?.name || "선택된 파일 없음"}</strong>
        </div>
        <div>
          <span>문서 타입</span>
          <strong>{DOC_TYPE_LABELS[docType]}</strong>
        </div>
      </div>

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
        disabled={!selectedFile || Boolean(fileError) || isAnalyzing}
        onClick={handleSubmit}
      >
        {isAnalyzing ? "분석 중" : "분석 시작"}
      </button>
    </section>
  );
}

export default UploadSection;
