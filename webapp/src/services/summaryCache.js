const SUMMARY_CACHE_PREFIX = "ai-summary:";

function getStorageKey(cacheKey) {
  return `${SUMMARY_CACHE_PREFIX}${cacheKey}`;
}

export function getCachedSummary(cacheKey) {
  return window.localStorage.getItem(getStorageKey(cacheKey)) ?? "";
}

export function setCachedSummary(cacheKey, summary) {
  window.localStorage.setItem(getStorageKey(cacheKey), summary);
}
