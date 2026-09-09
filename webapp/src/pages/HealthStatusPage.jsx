import { useCallback } from "react";
import { Link } from "react-router-dom";

import HealthStatus from "../components/HealthStatus";
import { getHealthStatus } from "../services/api";
import useAsyncResource from "../hooks/useAsyncResource";

export default function HealthStatusPage() {
  const loadHealthStatus = useCallback(({ signal }) => getHealthStatus({ signal }), []);
  const { data: health, isLoading, errorMessage } = useAsyncResource(
    loadHealthStatus,
    "Unable to load health status.",
  );

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">NewPage Careers</p>
        <h1>Health status</h1>
        <p className="hero-copy">Live status from the backend /health endpoint.</p>
        <Link className="back-link" to="/jobs">
          Back to all roles
        </Link>
      </header>

      <HealthStatus health={health} isLoading={isLoading} errorMessage={errorMessage} />
    </main>
  );
}
