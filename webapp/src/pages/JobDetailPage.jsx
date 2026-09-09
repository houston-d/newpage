import { useCallback } from "react";

import { getJobById } from "../services/api";
import useAsyncResource from "../hooks/useAsyncResource";

export default function JobDetailPage({ jobId }) {
  const loadJob = useCallback(({ signal }) => getJobById(jobId, { signal }), [jobId]);
  const { data: job, isLoading, errorMessage } = useAsyncResource(loadJob, "Unable to load job.");

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
      ) : null}
    </main>
  );
}
