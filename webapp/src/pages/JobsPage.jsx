import { useEffect, useState } from "react";

import { getJobs } from "../services/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isActive = true;

    const loadJobs = async () => {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const availableJobs = await getJobs();
        if (isActive) {
          setJobs(availableJobs);
        }
      } catch (error) {
        if (isActive) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load jobs.");
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadJobs();
    return () => {
      isActive = false;
    };
  }, []);

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
        jobs.length > 0 ? (
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
