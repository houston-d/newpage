const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function getJobs() {
  const response = await fetch(`${API_BASE_URL}/jobs`);
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(`Unexpected response from job-service (/jobs): HTTP ${response.status}`);
  }
  const payload = await response.json();

  if (!response.ok) {
    const message = payload?.message ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (!Array.isArray(payload?.jobs)) {
    throw new Error("Invalid jobs payload received from job-service.");
  }

  return payload.jobs;
}

export async function getJobById(id) {
  const response = await fetch(`${API_BASE_URL}/jobs/${encodeURIComponent(id)}`);
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(`Unexpected response from job-service (/jobs/${id}): HTTP ${response.status}`);
  }
  const payload = await response.json();

  if (!response.ok) {
    const message = payload?.message ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (!payload?.job || typeof payload.job !== "object") {
    throw new Error("Invalid job payload received from job-service.");
  }

  return payload.job;
}

export async function getHealthStatus() {
  const response = await fetch(`${API_BASE_URL}/health`);
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(`Unexpected response from job-service (/health): HTTP ${response.status}`);
  }
  const payload = await response.json();

  if (typeof payload?.status !== "number" || typeof payload?.message !== "string") {
    throw new Error("Invalid health payload received from job-service.");
  }

  return {
    httpStatus: response.status,
    status: payload.status,
    message: payload.message,
  };
}