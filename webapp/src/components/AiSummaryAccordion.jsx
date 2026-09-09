import { useEffect, useState } from "react";

import { getCachedSummary, setCachedSummary } from "../services/summaryCache";
import {renderDescriptionWithBoldMarkdown} from "../services/renderText.jsx";

export default function AiSummaryAccordion({ cacheKey, generateSummary }) {
  const [summary, setSummary] = useState(() => getCachedSummary(cacheKey));
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [summaryErrorMessage, setSummaryErrorMessage] = useState("");

  useEffect(() => {
    setSummary(getCachedSummary(cacheKey));
    setSummaryErrorMessage("");
    setIsGeneratingSummary(false);
  }, [cacheKey]);

  const handleGenerateSummary = async () => {
    setIsGeneratingSummary(true);
    setSummaryErrorMessage("");
    setSummary("");

    try {
      const generatedSummary = await generateSummary();
      setSummary(generatedSummary);
      setCachedSummary(cacheKey, generatedSummary);
    } catch (error) {
      console.error(error);
      setSummaryErrorMessage("failed to generate summary");
    } finally {
      setIsGeneratingSummary(false);
    }
  };

  return (
    <details className="summary-accordion">
      <summary>AI summary</summary>
      <div className="summary-panel">
        <button
          className="summary-generate-button"
          type="button"
          onClick={handleGenerateSummary}
          disabled={isGeneratingSummary}
        >
          {isGeneratingSummary ? "Generating..." : "Generate"}
        </button>
        {isGeneratingSummary ? <p className="state">Generating summary...</p> : null}
        {summaryErrorMessage ? <p className="state error">{summaryErrorMessage}</p> : null}
        {summary ? <p className="summary-text">{renderDescriptionWithBoldMarkdown(summary)}</p> : null}
      </div>
    </details>
  );
}
