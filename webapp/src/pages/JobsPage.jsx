import { useCallback, useState } from "react";

import { getJobs, queryJobBoardSummary } from "../services/api";
import { getCachedSummary, setCachedSummary } from "../services/summaryCache";
import useAsyncResource from "../hooks/useAsyncResource";

const JOBS_SUMMARY_CACHE_KEY = "jobs-page";

export default function JobsPage() {
  const loadJobs = useCallback(({ signal }) => getJobs({ signal }), []);
  const { data: jobs, isLoading, errorMessage } = useAsyncResource(loadJobs, "Unable to load jobs.");
  const [summary, setSummary] = useState(() => getCachedSummary(JOBS_SUMMARY_CACHE_KEY));
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [summaryErrorMessage, setSummaryErrorMessage] = useState("");

  const handleGenerateSummary = async () => {
    setIsGeneratingSummary(true);
    setSummaryErrorMessage("");

    try {
      const generatedSummary = await queryJobBoardSummary();
      setSummary(generatedSummary);
      setCachedSummary(JOBS_SUMMARY_CACHE_KEY, generatedSummary);
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
        <h1>Open roles</h1>
        <p className="hero-copy">Browse current opportunities powered by the job-service.</p>
      </header>

      {isLoading ? <p className="state">Loading jobs...</p> : null}
      {errorMessage ? <p className="state error">{errorMessage}</p> : null}

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

      {!isLoading && !errorMessage ? (
        jobs && jobs.length > 0 ? (
          <section className="jobs-grid" aria-label="Available jobs">
            {jobs.map((job) => (
              <article className="job-card" key={job.id}>
                <div className="job-meta">
                  <span>{job.company}</span>
                  <span>{job.location}</span>
                </div>
                <h2>{job.title}</h2>
                <p className="salary">{job.salary}</p>
                <p className="description">{job.jd}</p>
                <a className="job-link" href={`/jobs/${encodeURIComponent(job.id)}`}>
                  View role
                </a>
              </article>
            ))}
          </section>
        ) : (
          <p className="state">No jobs are currently available.</p>
        )
      ) : null}

      <a className="back-link" href="/health">
        View backend health
      </a>
    </main>
  );
}
