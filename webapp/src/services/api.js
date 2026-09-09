const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

function assertJsonResponse(response, endpoint, fallbackErrorMessage) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(`${fallbackErrorMessage} (unexpected response format from ${endpoint}).`);
  }
}

function buildHttpErrorMessage(baseMessage, status) {
  return `${baseMessage} (HTTP ${status}).`;
}

export async function getJobs(options = {}) {
  const response = await fetch(`${API_BASE_URL}/jobs`, { signal: options.signal });
  assertJsonResponse(response, "/jobs", "Unable to load jobs");
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(buildHttpErrorMessage("Unable to load jobs", response.status));
  }

  if (!Array.isArray(payload?.jobs)) {
    throw new Error("Invalid jobs payload received from job-service.");
  }

  return payload.jobs;
}

export async function getJobById(id, options = {}) {
  const response = await fetch(`${API_BASE_URL}/jobs/${encodeURIComponent(id)}`, { signal: options.signal });
  assertJsonResponse(response, "/jobs/:id", "Unable to load job");
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(buildHttpErrorMessage("Unable to load job", response.status));
  }

  if (!payload?.job || typeof payload.job !== "object") {
    throw new Error("Invalid job payload received from job-service.");
  }

  return payload.job;
}

export async function getHealthStatus(options = {}) {
  const response = await fetch(`${API_BASE_URL}/health`, { signal: options.signal });
  assertJsonResponse(response, "/health", "Unable to load health status");
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(buildHttpErrorMessage("Unable to load health status", response.status));
  }

  if (typeof payload?.status !== "number" || typeof payload?.message !== "string") {
    throw new Error("Invalid health payload received from job-service.");
  }

  return {
    httpStatus: response.status,
    status: payload.status,
    message: payload.message,
  };
}