import { useEffect, useState } from "react";

function isAbortError(error) {
  const isDomAbortError =
    typeof DOMException !== "undefined" && error instanceof DOMException && error.name === "AbortError";

  return (
    isDomAbortError ||
    (typeof error === "object" && error !== null && "name" in error && error.name === "AbortError")
  );
}

export default function useAsyncResource(loadResource, fallbackErrorMessage) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isActive = true;
    const abortController = new AbortController();

    const load = async () => {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const loadedData = await loadResource({ signal: abortController.signal });
        if (isActive) {
          setData(loadedData);
        }
      } catch (error) {
        if (isAbortError(error)) {
          return;
        }

        console.error(error);
        if (isActive) {
          setErrorMessage(fallbackErrorMessage);
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    load();
    return () => {
      isActive = false;
      abortController.abort();
    };
  }, [fallbackErrorMessage, loadResource]);

  return { data, isLoading, errorMessage };
}
