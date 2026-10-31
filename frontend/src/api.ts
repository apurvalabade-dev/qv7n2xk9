import { useEffect, useState } from "react";

// Empty in local dev (Vite proxies /api). Set VITE_API_URL at build time for deployment.
const BASE: string = import.meta.env.VITE_API_URL ?? "";

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export function useApi<T>(path: string) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    const ctrl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    getJson<T>(path, ctrl.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setState({ data: null, error: e instanceof Error ? e.message : String(e), loading: false });
      });
    return () => ctrl.abort();
  }, [path]);

  return state;
}