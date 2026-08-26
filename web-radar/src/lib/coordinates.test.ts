import { describe, expect, it } from 'vitest';
import { projectWorldPoint } from './coordinates';

describe('projectWorldPoint', () => {
  const map = { origin: { x: 0, y: 1024 }, scale: 1 };

  it('projects a world point to normalized radar coordinates', () => {
    expect(projectWorldPoint({ x: 512, y: 512, z: 0 }, map)).toEqual({
      x: 0.5,
      y: 0.5,
      inBounds: true,
    });
  });

  it('marks out-of-bounds points', () => {
    expect(projectWorldPoint({ x: 2000, y: 0, z: 0 }, map).inBounds).toBe(false);
  });
});
