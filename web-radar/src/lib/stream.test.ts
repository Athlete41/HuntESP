import { describe, expect, it } from 'vitest';
import { deriveWebSocketUrl, reconnectDelayMs } from './stream';

describe('stream helpers', () => {
  it('derives a same-origin WebSocket URL', () => {
    expect(deriveWebSocketUrl({ protocol: 'http:', host: 'localhost:8080' })).toBe(
      'ws://localhost:8080/api/v1/stream',
    );
    expect(deriveWebSocketUrl({ protocol: 'https:', host: 'radar.example' })).toBe(
      'wss://radar.example/api/v1/stream',
    );
  });

  it('keeps reconnect delays bounded', () => {
    expect(reconnectDelayMs(0, 0)).toBeGreaterThanOrEqual(400);
    expect(reconnectDelayMs(0, 0)).toBeLessThanOrEqual(600);
    expect(reconnectDelayMs(20, 1)).toBeLessThanOrEqual(14_000);
  });
});
