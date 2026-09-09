import { useEffect, useState } from "react";

import { getJobById } from "../services/api";

export default function JobDetailPage({ jobId }) {
  const [job, setJob] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isActive = true;

    const loadJob = async () => {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const loadedJob = await getJobById(jobId);
        if (isActive) {
          setJob(loadedJob);
        }
      } catch (error) {
        if (isActive) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load job.");
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadJob();
    return () => {
      isActive = false;
    };
  }, [jobId]);

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
