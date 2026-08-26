import { useEffect, useState, type CSSProperties } from 'react';
import { projectWorldPoint } from '../lib/coordinates';
import type { Entity, MapDefinition } from '../types/protocol';

interface RadarMapProps {
  mapId: string;
  map: MapDefinition | undefined;
  entities: Entity[];
  manifestLoading: boolean;
  manifestError: string | null;
  onRetryMap: () => void;
}

const entityColors: Record<string, string> = {
  LocalPlayer: '#4ade80',
  FriendlyPlayer: '#60a5fa',
  EnemyPlayer: '#f87171',
  DeadPlayer: '#9ca3af',
  Assassin: '#fb923c',
  Butcher: '#fb923c',
  Spider: '#fb923c',
  Scrapbeak: '#fb923c',
  Rotjaw: '#fb923c',
  Hellborn: '#fb923c',
};

function entityColor(type: string): string {
  return entityColors[type] ?? '#e5e7eb';
}

export function RadarMap({
  mapId,
  map,
  entities,
  manifestLoading,
  manifestError,
  onRetryMap,
}: RadarMapProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = map?.image ?? (mapId ? `/maps/${encodeURIComponent(mapId)}/radar.png` : '');

  useEffect(() => {
    setImageFailed(false);
  }, [imageUrl]);

  return (
    <section className="radar-shell" aria-label="雷达">
      <div className="radar-topbar">
        <strong>{map?.name ?? (mapId || '等待地图')}</strong>
        <span>{entities.length} 个实体</span>
      </div>

      <div className="radar-frame">
        <div className="radar-surface">
          {map && !imageFailed && (
            <img
              className="radar-image"
              src={imageUrl}
              alt=""
              aria-hidden="true"
              draggable={false}
              onError={() => setImageFailed(true)}
            />
          )}

          {map &&
            entities.map((entity) => {
              if (!entity.position) return null;
              const point = projectWorldPoint(entity.position, map);
              if (!point.inBounds) return null;
              const style = {
                left: `${point.x * 100}%`,
                top: `${point.y * 100}%`,
                '--entity-color': entityColor(entity.type),
              } as CSSProperties;
              return (
                <div
                  className={`map-entity type-${entity.type}`}
                  style={style}
                  key={entity.id}
                  title={entity.type}
                />
              );
            })}

          {!map && (
            <div className="map-placeholder">
              <strong>
                {manifestLoading
                  ? '正在加载地图清单'
                  : mapId
                    ? `缺少 ${mapId} 的地图定义`
                    : '等待地图'}
              </strong>
              {manifestError && (
                <>
                  <p>{manifestError}</p>
                  <button type="button" onClick={onRetryMap}>
                    重新加载地图清单
                  </button>
                </>
              )}
            </div>
          )}

          {map && imageFailed && (
            <div className="map-placeholder">
              <strong>地图图片加载失败</strong>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
