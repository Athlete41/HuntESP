export type StreamStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export function deriveWebSocketUrl(location: {
  protocol: string;
  host: string;
}): string {
  const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${location.host}/api/v1/stream`;
}

export function reconnectDelayMs(attempt: number, jitter = Math.random()): number {
  const base = Math.min(10_000, 500 * 2 ** Math.max(0, attempt));
  const normalizedJitter = Math.min(1, Math.max(0, jitter));
  return Math.round(base * (0.8 + normalizedJitter * 0.4));
}
