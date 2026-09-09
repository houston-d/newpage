import { useEffect, useState } from "react";

import HealthStatus from "../components/HealthStatus";
import { getHealthStatus } from "../services/api";

export default function HealthStatusPage() {
  const [health, setHealth] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isActive = true;

    const loadHealthStatus = async () => {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const loadedHealth = await getHealthStatus();
        if (isActive) {
          setHealth(loadedHealth);
        }
      } catch (error) {
        if (isActive) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load health status.");
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadHealthStatus();
    return () => {
      isActive = false;
    };
  }, []);

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">NewPage Careers</p>
        <h1>Health status</h1>
        <p className="hero-copy">Live status from the backend /health endpoint.</p>
        <a className="back-link" href="/jobs">
          Back to all roles
        </a>
      </header>

      <HealthStatus health={health} isLoading={isLoading} errorMessage={errorMessage} />
    </main>
  );
}
