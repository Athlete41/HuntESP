export const PROTOCOL_VERSION = 1 as const;

export const PLAYER_TYPES = [
  'LocalPlayer',
  'FriendlyPlayer',
  'EnemyPlayer',
  'DeadPlayer',
] as const;

export const BOSS_TYPES = [
  'Assassin',
  'Butcher',
  'Spider',
  'Scrapbeak',
  'Rotjaw',
  'Hellborn',
] as const;

export type PlayerType = (typeof PLAYER_TYPES)[number];
export type BossType = (typeof BOSS_TYPES)[number];
export type EntityType = PlayerType | BossType | 'Other';

export function isBossType(type: string): type is BossType {
  return (BOSS_TYPES as readonly string[]).includes(type);
}

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

export interface Entity {
  id: string;
  type: EntityType;
  position: Vector3 | null;
}

export interface HelloMessage {
  v: typeof PROTOCOL_VERSION;
  type: 'hello';
  serverTimeMs: number;
  updateHz?: number;
}

export interface SnapshotMessage {
  v: typeof PROTOCOL_VERSION;
  type: 'snapshot';
  seq: number;
  capturedAtMs: number;
  map: { id: string };
  entities: Entity[];
}

export interface ErrorMessage {
  v: typeof PROTOCOL_VERSION;
  type: 'error';
  code: string;
  message: string;
}

export type ServerMessage = HelloMessage | SnapshotMessage | ErrorMessage;

export interface MapDefinition {
  id: string;
  name: string;
  origin: { x: number; y: number };
  scale: number;
  image?: string;
}

export interface MapManifest {
  version: 1;
  maps: MapDefinition[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isVector3(value: unknown): value is Vector3 {
  return (
    isRecord(value) &&
    isFiniteNumber(value.x) &&
    isFiniteNumber(value.y) &&
    isFiniteNumber(value.z)
  );
}

function isEntity(value: unknown): value is Entity {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.type !== 'string') {
    return false;
  }
  return value.position === undefined || value.position === null || isVector3(value.position);
}

export function parseServerMessage(raw: string): ServerMessage | null {
  let value: unknown;
  try {
    value = JSON.parse(raw) as unknown;
  } catch {
    return null;
  }

  if (!isRecord(value) || value.v !== PROTOCOL_VERSION || typeof value.type !== 'string') {
    return null;
  }

  if (value.type === 'hello') {
    return isFiniteNumber(value.serverTimeMs) ? (value as unknown as HelloMessage) : null;
  }

  if (value.type === 'error') {
    return typeof value.code === 'string' && typeof value.message === 'string'
      ? (value as unknown as ErrorMessage)
      : null;
  }

  if (value.type !== 'snapshot') return null;
  if (!isRecord(value.map) || typeof value.map.id !== 'string') return null;
  if (!Array.isArray(value.entities) || !value.entities.every(isEntity)) return null;
  if (!isFiniteNumber(value.seq) || !isFiniteNumber(value.capturedAtMs)) return null;

  return value as unknown as SnapshotMessage;
}

export function isMapManifest(value: unknown): value is MapManifest {
  if (!isRecord(value) || value.version !== 1 || !Array.isArray(value.maps)) return false;
  return value.maps.every((map) => {
    if (!isRecord(map) || !isRecord(map.origin)) return false;
    return (
      typeof map.id === 'string' &&
      typeof map.name === 'string' &&
      isFiniteNumber(map.origin.x) &&
      isFiniteNumber(map.origin.y) &&
      isFiniteNumber(map.scale) &&
      map.scale > 0 &&
      (map.image === undefined || typeof map.image === 'string')
    );
  });
}
