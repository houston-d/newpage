import JobDetailPage from "./pages/JobDetailPage";
import JobsPage from "./pages/JobsPage";
import HealthStatusPage from "./pages/HealthStatusPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  if (window.location.pathname === "/jobs") {
    return <JobsPage />;
  }

  if (window.location.pathname === "/health") {
    return <HealthStatusPage />;
  }

  const jobPathMatch = window.location.pathname.match(/^\/jobs\/([^/]+)$/);
  if (jobPathMatch) {
    return <JobDetailPage jobId={decodeURIComponent(jobPathMatch[1])} />;
  }

  return <NotFoundPage />;
}