import { useCallback, useEffect, useState } from "react";

import { analyseJobSummary, getJobById } from "../services/api";
import { getCachedSummary, setCachedSummary } from "../services/summaryCache";
import useAsyncResource from "../hooks/useAsyncResource";

export default function JobDetailPage({ jobId }) {
  const loadJob = useCallback(({ signal }) => getJobById(jobId, { signal }), [jobId]);
  const { data: job, isLoading, errorMessage } = useAsyncResource(loadJob, "Unable to load job.");
  const summaryCacheKey = `job-detail:${jobId}`;
  const [summary, setSummary] = useState(() => getCachedSummary(summaryCacheKey));
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [summaryErrorMessage, setSummaryErrorMessage] = useState("");

  useEffect(() => {
    setSummary(getCachedSummary(summaryCacheKey));
    setSummaryErrorMessage("");
    setIsGeneratingSummary(false);
  }, [summaryCacheKey]);

  const handleGenerateSummary = async () => {
    if (!job) {
      return;
    }

    setIsGeneratingSummary(true);
    setSummary("");
    setSummaryErrorMessage("");

    try {
      const generatedSummary = await analyseJobSummary(job.jd);
      setSummary(generatedSummary);
      setCachedSummary(summaryCacheKey, generatedSummary);
    } catch (error) {
      console.error(error);
      setSummaryErrorMessage("failed to generate summary");
    } finally {
      setIsGeneratingSummary(false);
    }
  };

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">NewPage Careers</p>
        <h1>Job details</h1>
        <a className="back-link" href="/jobs">
          Back to all roles
        </a>
      </header>

      {isLoading ? <p className="state">Loading job...</p> : null}
      {errorMessage ? <p className="state error">{errorMessage}</p> : null}

      {!isLoading && !errorMessage && job ? (
        <>
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
              {summary ? <p className="summary-text">{summary}</p> : null}
            </div>
          </details>

          <article className="job-detail">
            <div className="job-meta">
              <span>{job.company}</span>
              <span>{job.location}</span>
            </div>
            <h2>{job.title}</h2>
            <p className="salary">{job.salary}</p>
            <p className="detail-description">{job.jd}</p>
            <button className="apply-button" type="button">
              Apply
            </button>
          </article>
        </>
      ) : null}
    </main>
  );
}
