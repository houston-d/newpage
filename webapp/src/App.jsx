import { Route, Routes, useParams } from "react-router-dom";

import JobDetailPage from "./pages/JobDetailPage";
import JobsPage from "./pages/JobsPage";
import HealthStatusPage from "./pages/HealthStatusPage";
import NotFoundPage from "./pages/NotFoundPage";
import ChatPage from "./pages/ChatPage";

function JobDetailRoute() {
  const { jobId } = useParams();
  const encodedId = jobId ?? "";

  try {
    const decodedId = decodeURIComponent(encodedId);
    return <JobDetailPage jobId={decodedId} />;
  } catch {
    return <NotFoundPage />;
  }
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<JobsPage />} />
      <Route path="/jobs" element={<JobsPage />} />
      <Route path="/health" element={<HealthStatusPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/jobs/:jobId" element={<JobDetailRoute />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}