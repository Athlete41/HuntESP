import { useCallback, useEffect, useRef, useState } from 'react';
import { isMapManifest, type MapManifest } from '../types/protocol';

interface MapManifestState {
  manifest: MapManifest | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

export function useMapManifest(): MapManifestState {
  const [manifest, setManifest] = useState<MapManifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);
  const retryAttempt = useRef(0);

  const retry = useCallback(() => {
    retryAttempt.current = 0;
    setRequestVersion((version) => version + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let retryTimer: number | undefined;
    setLoading(true);
    setError(null);

    fetch('/maps/manifest.json', { cache: 'no-cache', signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<unknown>;
      })
      .then((value) => {
        if (!isMapManifest(value)) throw new Error('manifest 格式不符合 v1');
        retryAttempt.current = 0;
        setManifest(value);
        setLoading(false);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        const message = reason instanceof Error ? reason.message : '未知错误';
        setLoading(false);
        setError(message);
        const delay = Math.min(30_000, 1_000 * (2 ** retryAttempt.current++));
        retryTimer = window.setTimeout(() => {
          setRequestVersion((version) => version + 1);
        }, delay);
      });

    return () => {
      controller.abort();
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
    };
  }, [requestVersion]);

  return { manifest, loading, error, retry };
}
