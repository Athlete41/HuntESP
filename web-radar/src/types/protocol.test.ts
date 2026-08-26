import { describe, expect, it } from 'vitest';
import { parseServerMessage } from './protocol';

const validSnapshot = {
  v: 1,
  type: 'snapshot',
  seq: 42,
  capturedAtMs: 100_500,
  map: { id: 'bayou' },
  entities: [
    { id: '0x1234', type: 'LocalPlayer', position: { x: 1, y: 2, z: 3 } },
    { id: '0x5678', type: 'Butcher', position: { x: 4, y: 5, z: 6 } },
  ],
};

describe('parseServerMessage', () => {
  it('accepts a structurally valid v1 snapshot', () => {
    const parsed = parseServerMessage(JSON.stringify(validSnapshot));
    expect(parsed?.type).toBe('snapshot');
    if (parsed?.type === 'snapshot') {
      expect(parsed.entities).toHaveLength(2);
      expect(parsed.entities[0].type).toBe('LocalPlayer');
      expect(parsed.entities[1].type).toBe('Butcher');
    }
  });

  it('accepts an empty entities list', () => {
    const parsed = parseServerMessage(JSON.stringify({ ...validSnapshot, entities: [] }));
    expect(parsed?.type).toBe('snapshot');
  });

  it('rejects other versions, malformed entities and invalid JSON', () => {
    expect(parseServerMessage(JSON.stringify({ ...validSnapshot, v: 2 }))).toBeNull();
    const invalid = {
      ...validSnapshot,
      entities: [{ id: '0x1', type: 'LocalPlayer', position: { x: '1', y: 2, z: 3 } }],
    };
    expect(parseServerMessage(JSON.stringify(invalid))).toBeNull();
    expect(parseServerMessage('{nope')).toBeNull();
  });

  it('accepts hello and error control frames', () => {
    expect(parseServerMessage('{"v":1,"type":"hello","serverTimeMs":12}')?.type).toBe('hello');
    expect(
      parseServerMessage('{"v":1,"type":"error","code":"io","message":"denied"}')?.type,
    ).toBe('error');
  });

  it('accepts entities without a position', () => {
    const message = {
      ...validSnapshot,
      entities: [{ id: '0x9', type: 'EnemyPlayer', position: null }],
    };
    expect(parseServerMessage(JSON.stringify(message))?.type).toBe('snapshot');
  });

  it('rejects a snapshot without a map id', () => {
    const message = { ...validSnapshot, map: {} };
    expect(parseServerMessage(JSON.stringify(message))).toBeNull();
  });
});
