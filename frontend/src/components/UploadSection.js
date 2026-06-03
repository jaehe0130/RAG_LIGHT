import React from 'react';

function UploadSection({ onUpload }) {
  // 드래그 앤 드롭(Drag & Drop) 및 파일 선택 로직 구현 뼈대
  return (
    <div className="upload-section" style={{ border: '2px dashed #ccc', padding: '2rem' }}>
      <h2>문서 업로드 (약관/광고)</h2>
      
      <div className="drop-zone">
        <p>📥 여기에 파일을 드래그 앤 드롭하거나 클릭하여 업로드하세요.</p>
        {/* TODO: <input type="file" accept="image/*" /> 등 추가 */}
      </div>

      <div className="type-selector" style={{ marginTop: '1rem' }}>
        <p>분석할 문서의 타입을 선택하세요:</p>
        {/* TODO: 약관(CONTRACT) / 광고(AD)를 선택하는 라디오 버튼 혹은 토글 스위치 구현 */}
        <label>
          <input type="radio" name="docType" value="CONTRACT" defaultChecked /> 약관 진단
        </label>
        <label style={{ marginLeft: '1rem' }}>
          <input type="radio" name="docType" value="AD" /> 광고 탐지
        </label>
      </div>

      <button style={{ marginTop: '1rem' }} onClick={() => onUpload('dummyFile', 'CONTRACT')}>
        분석 시작하기 (API 호출)
      </button>
    </div>
  );
}

export default UploadSection;
