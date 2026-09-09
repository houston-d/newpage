import { useCallback } from "react";
import { Link } from "react-router-dom";

import AiSummaryAccordion from "../components/AiSummaryAccordion";
import { analyseJobSummary, getJobById } from "../services/api";
import useAsyncResource from "../hooks/useAsyncResource";

export default function JobDetailPage({ jobId }) {
  const loadJob = useCallback(({ signal }) => getJobById(jobId, { signal }), [jobId]);
  const { data: job, isLoading, errorMessage } = useAsyncResource(loadJob, "Unable to load job.");
  const summaryCacheKey = `job-detail:${jobId}`;

  return (
    <main className="page">
      <header className="hero">
        <div className="hero-header-row">
          <div>
            <p className="eyebrow">NewPage Careers</p>
            <h1>Job details</h1>
            <Link className="back-link" to="/jobs">
              Back to all roles
            </Link>
          </div>
          <Link className="chat-nav-button" to="/chat">
            Open AI chat
          </Link>
        </div>
      </header>

      {isLoading ? <p className="state">Loading job...</p> : null}
      {errorMessage ? <p className="state error">{errorMessage}</p> : null}

      {!isLoading && !errorMessage && job ? (
        <>
          <AiSummaryAccordion
            cacheKey={summaryCacheKey}
            generateSummary={() => analyseJobSummary(job.jd)}
          />

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
