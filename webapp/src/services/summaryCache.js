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

export function clearCachedSummaries() {
  const keysToRemove = [];

  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key?.startsWith(SUMMARY_CACHE_PREFIX)) {
      keysToRemove.push(key);
    }
  }

  for (const key of keysToRemove) {
    window.localStorage.removeItem(key);
  }
}
