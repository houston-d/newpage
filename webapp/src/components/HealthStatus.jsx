export default function HealthStatus({ health, isLoading, errorMessage }) {
  if (isLoading) {
    return <p className="state">Checking service health...</p>;
  }

  if (errorMessage) {
    return <p className="state error">{errorMessage}</p>;
  }

  if (!health) {
    return null;
  }

  const isHealthy = health.httpStatus === 200 && health.status === 200;

  return (
    <section className="health-card" aria-live="polite">
      <p className={`health-badge ${isHealthy ? "healthy" : "unhealthy"}`}>
        {isHealthy ? "Healthy" : "Unhealthy"}
      </p>
      <h2>Backend health endpoint</h2>
      <p className="health-message">{health.message}</p>
      <p className="health-meta">HTTP {health.httpStatus} · API status {health.status}</p>
    </section>
  );
}