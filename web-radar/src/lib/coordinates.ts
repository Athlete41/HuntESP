import type { MapDefinition, Vector3 } from '../types/protocol';

export interface RadarPoint {
  x: number;
  y: number;
  inBounds: boolean;
}

export function projectWorldPoint(
  point: Vector3,
  map: Pick<MapDefinition, 'origin' | 'scale'>,
  textureSize = 1024,
): RadarPoint {
  if (!Number.isFinite(textureSize) || textureSize <= 0 || map.scale <= 0) {
    return { x: 0, y: 0, inBounds: false };
  }

  const denominator = map.scale * textureSize;
  const x = (point.x - map.origin.x) / denominator;
  const y = (map.origin.y - point.y) / denominator;
  return {
    x,
    y,
    inBounds: x >= 0 && x <= 1 && y >= 0 && y <= 1,
  };
}
