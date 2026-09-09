import { useCallback } from "react";

import { getJobs } from "../services/api";
import useAsyncResource from "../hooks/useAsyncResource";

export default function JobsPage() {
  const loadJobs = useCallback(({ signal }) => getJobs({ signal }), []);
  const { data: jobs, isLoading, errorMessage } = useAsyncResource(loadJobs, "Unable to load jobs.");

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">NewPage Careers</p>
        <h1>Open roles</h1>
        <p className="hero-copy">Browse current opportunities powered by the job-service.</p>
      </header>

      {isLoading ? <p className="state">Loading jobs...</p> : null}
      {errorMessage ? <p className="state error">{errorMessage}</p> : null}

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
