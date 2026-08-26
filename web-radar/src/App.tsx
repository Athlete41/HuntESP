import { RadarMap } from './components/RadarMap';
import { useMapManifest } from './hooks/useMapManifest';
import { useRadarStream } from './hooks/useRadarStream';
import type { StreamStatus } from './lib/stream';
import { isBossType } from './types/protocol';

const statusLabel: Record<StreamStatus, string> = {
  connecting: '连接中',
  connected: '已连接',
  reconnecting: '重连中',
  disconnected: '已断开',
};

export default function App() {
  const stream = useRadarStream();
  const maps = useMapManifest();
  const snapshot = stream.frame?.snapshot;
  const mapId = snapshot?.map.id ?? '';
  const map = maps.manifest?.maps.find((entry) => entry.id === mapId);
  const entities = snapshot?.entities ?? [];
  const players = entities.filter((entity) => !isBossType(entity.type));
  const bosses = entities.filter((entity) => isBossType(entity.type));

  return (
    <div className="app-shell">
      <header className="app-header">
        <strong>Hunt Radar</strong>
        <span className={`status-dot ${stream.status}`} aria-hidden="true" />
        <span className="map-name">{map?.name ?? (mapId || '等待地图')}</span>
        <span className="counts">
          {players.length} 玩家 / {bosses.length} Boss
        </span>
      </header>

      <main className="radar-layout">
        <RadarMap
          mapId={mapId}
          map={map}
          entities={entities}
          manifestLoading={maps.loading}
          manifestError={maps.error}
          onRetryMap={maps.retry}
        />
      </main>

      <footer className="app-footer">
        <span>协议 v1</span>
        <span>{statusLabel[stream.status]}</span>
        {stream.error && <span className="error-text">{stream.error}</span>}
      </footer>
    </div>
  );
}
