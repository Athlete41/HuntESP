import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { deriveWebSocketUrl, reconnectDelayMs, type StreamStatus } from '../lib/stream';
import { parseServerMessage, type SnapshotMessage } from '../types/protocol';

export interface RadarFrame {
  snapshot: SnapshotMessage;
  receivedAtWallMs: number;
}

export interface RadarStreamState {
  status: StreamStatus;
  frame: RadarFrame | null;
  error: string | null;
  retry: () => void;
}

export function useRadarStream(): RadarStreamState {
  const url = useMemo(() => deriveWebSocketUrl(window.location), []);
  const [status, setStatus] = useState<StreamStatus>('connecting');
  const [frame, setFrame] = useState<RadarFrame | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryVersion, setRetryVersion] = useState(0);
  const attemptRef = useRef(0);

  const retry = useCallback(() => setRetryVersion((version) => version + 1), []);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | undefined;
    let reconnectTimer: number | undefined;

    const clearReconnect = () => {
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      reconnectTimer = undefined;
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      setStatus('reconnecting');
      const delay = reconnectDelayMs(attemptRef.current++);
      reconnectTimer = window.setTimeout(connect, delay);
    };

    function connect() {
      if (disposed) return;
      clearReconnect();
      setStatus(attemptRef.current === 0 ? 'connecting' : 'reconnecting');
      let candidate: WebSocket;
      try {
        candidate = new WebSocket(url);
      } catch {
        setError('WebSocket 连接创建失败');
        scheduleReconnect();
        return;
      }
      socket = candidate;

      candidate.addEventListener('open', () => {
        if (disposed) return;
        setStatus('connected');
        setError(null);
      });

      candidate.addEventListener('message', (event) => {
        if (disposed) return;
        if (typeof event.data !== 'string') return;
        const message = parseServerMessage(event.data);
        if (!message) {
          setError('无法识别的数据帧');
          return;
        }
        if (message.type === 'error') {
          setError(`${message.code}: ${message.message}`);
          return;
        }
        if (message.type !== 'snapshot') return;
        attemptRef.current = 0;
        setFrame({ snapshot: message, receivedAtWallMs: Date.now() });
        setError(null);
      });

      candidate.addEventListener('close', () => {
        if (disposed) return;
        socket = undefined;
        setStatus('disconnected');
        scheduleReconnect();
      });

      candidate.addEventListener('error', () => {
        if (disposed) return;
        setError('无法连接雷达服务');
      });
    }

    connect();
    return () => {
      disposed = true;
      clearReconnect();
      if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) {
        try {
          socket.close();
        } catch {
          // CONNECTING sockets can reject close() in some engines.
        }
      }
    };
  }, [retryVersion, url]);

  return { status, frame, error, retry };
}
