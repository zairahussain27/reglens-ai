import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../services/api";

/** GET a path; exposes loading/error and a reload(). Stale responses are ignored. */
export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!path);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    if (!path) return;
    let active = true;
    setLoading(true);
    api<T>(path)
      .then((value) => { if (active) { setData(value); setError(""); } })
      .catch((e) => { if (active) setError(errorMessage(e, "Unable to load data")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, version]);

  return { data, error, loading, reload, setData };
}
