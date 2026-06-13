import React from "react";

function SuggestedQuestionChips({ questions, onSelect, disabled = false }) {
  return (
    <div className="suggested-chips" aria-label="추천 질문">
      {questions.map((question) => (
        <button key={question} type="button" className="chip-button" disabled={disabled} onClick={() => onSelect(question)}>
          {question}
        </button>
      ))}
    </div>
  );
}

export default SuggestedQuestionChips;
