import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export function useResource<T>(path: string | null, initial: T) {
  const [data, setData] = useState<T>(initial);
  const [loading, setLoading] = useState(!!path);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(0);
  const initialRef = useRef(initial);
  const reload = useCallback(async () => {
    const request = ++sequence.current;
    if (!path) {
      setLoading(false);
      setError(null);
      setData(initialRef.current);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api<T>(path);
      if (request === sequence.current) setData(result);
    } catch (problem) {
      if (request === sequence.current)
        setError(
          problem instanceof Error
            ? problem.message
            : "Não foi possível carregar.",
        );
    } finally {
      if (request === sequence.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    setData(initialRef.current);
    void reload();
    return () => {
      sequence.current += 1;
    };
  }, [reload]);
  return { data, loading, error, reload, setData };
}
