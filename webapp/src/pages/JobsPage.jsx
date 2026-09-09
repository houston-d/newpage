import { useCallback } from "react";
import { Link } from "react-router-dom";

import AiSummaryAccordion from "../components/AiSummaryAccordion";
import { getJobs, queryJobBoardSummary } from "../services/api";
import useAsyncResource from "../hooks/useAsyncResource";
import { renderDescriptionWithBoldMarkdown } from "../services/renderText.jsx";

const JOBS_SUMMARY_CACHE_KEY = "jobs-page";
const JOB_DESCRIPTION_PREVIEW_LIMIT = 300;
const EMPTY_SALARY_PLACEHOLDER = "\u00A0";

function getJobDescriptionPreview(description) {
  if (typeof description !== "string") {
    return "";
  }

  if (description.length <= JOB_DESCRIPTION_PREVIEW_LIMIT) {
    return description;
  }

  return `${description.slice(0, JOB_DESCRIPTION_PREVIEW_LIMIT)}...`;
}

function getJobSalaryDisplay(salary) {
  if (typeof salary !== "string" || salary.trim().length === 0) {
    return EMPTY_SALARY_PLACEHOLDER;
  }

  return salary;
}

export default function JobsPage() {
  const loadJobs = useCallback(({ signal }) => getJobs({ signal }), []);
  const { data: jobs, isLoading, errorMessage } = useAsyncResource(loadJobs, "Unable to load jobs.");

  return (
    <main className="page">
      <header className="hero">
        <div className="hero-header-row">
          <div>
            <p className="eyebrow">NewPage Careers</p>
            <h1>Open roles</h1>
            <p className="hero-copy">Browse current opportunities powered by the job-service.</p>
          </div>
          <Link className="chat-nav-button" to="/chat">
            Open AI chat
          </Link>
        </div>
      </header>

      {isLoading ? <p className="state">Loading jobs...</p> : null}
      {errorMessage ? <p className="state error">{errorMessage}</p> : null}

      <AiSummaryAccordion cacheKey={JOBS_SUMMARY_CACHE_KEY} generateSummary={queryJobBoardSummary} />

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
                <p className="salary">{getJobSalaryDisplay(job.salary)}</p>
                <p className="description">{renderDescriptionWithBoldMarkdown(getJobDescriptionPreview(job.jd))}</p>
                <Link className="job-link" to={`/jobs/${encodeURIComponent(job.id)}`}>
                  View role
                </Link>
              </article>
            ))}
          </section>
        ) : (
          <p className="state">No jobs are currently available.</p>
        )
      ) : null}

      <hr className="back-link-divider" />
      <Link className="back-link" to="/health">
        View backend health
      </Link>
    </main>
  );
}
