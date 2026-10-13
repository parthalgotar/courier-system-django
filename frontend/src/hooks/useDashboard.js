import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

export function useDashboard(filters = {}) {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const isFirstMount = useRef(true);

  // Serialized filters key for change detection
  const filtersKey = JSON.stringify(filters);

  const fetchData = useCallback(
    async (signal, { silent = false } = {}) => {
      if (!token) return;
      if (!silent) setLoading(true);
      setError(null);

      try {
        const res = await api.getDashboardSummary(token, filters, signal);
        setData(res);
        setError(null);
      } catch (err) {
        if (err.name === "AbortError") return;
        setError(err.message || "Failed to load dashboard data.");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [token, filtersKey] // eslint-disable-line react-hooks/exhaustive-deps
  );

  // Initial and on-filter-change fetch
  useEffect(() => {
    const controller = new AbortController();
    fetchData(controller.signal, { silent: !isFirstMount.current });
    isFirstMount.current = false;
    return () => controller.abort();
  }, [fetchData]);

  // Auto refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchData(undefined, { silent: true });
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const refetch = useCallback(() => {
    return fetchData(undefined, { silent: false });
  }, [fetchData]);

  return { data, loading, error, refetch };
}
