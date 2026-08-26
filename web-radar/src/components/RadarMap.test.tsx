import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { Entity, MapDefinition } from '../types/protocol';
import { RadarMap } from './RadarMap';

const map: MapDefinition = {
  id: 'bayou',
  name: 'Bayou',
  origin: { x: 0, y: 1024 },
  scale: 1,
  image: '/maps/bayou/radar.png',
};

function entity(overrides: Partial<Entity>): Entity {
  return {
    id: '0x1',
    type: 'LocalPlayer',
    position: { x: 512, y: 512, z: 0 },
    ...overrides,
  };
}

function radarElement(entities: Entity[], radarMap?: MapDefinition) {
  return createElement(RadarMap, {
    mapId: radarMap?.id ?? 'bayou',
    map: radarMap,
    entities,
    manifestLoading: false,
    manifestError: null,
    onRetryMap: () => {},
  });
}

function renderEntities(entities: Entity[], radarMap?: MapDefinition): string {
  return renderToStaticMarkup(radarElement(entities, radarMap));
}

describe('RadarMap entities', () => {
  it('renders the map image and every positioned entity marker', () => {
    const html = renderEntities([
      entity({ id: 'local', type: 'LocalPlayer' }),
      entity({ id: 'boss', type: 'Butcher' }),
      entity({ id: 'ghost', type: 'EnemyPlayer', position: null }),
    ], map);

    expect(html).toContain('src="/maps/bayou/radar.png"');
    expect(html.match(/class="map-entity/g)).toHaveLength(2);
    expect(html).toContain('type-LocalPlayer');
    expect(html).toContain('type-Butcher');
  });

  it('skips markers outside the map bounds', () => {
    const html = renderEntities([
      entity({ id: 'outside', position: { x: 99999, y: 99999, z: 0 } }),
    ], map);
    expect(html.match(/class="map-entity/g)).toBeNull();
  });

  it('shows a placeholder when the map is unknown', () => {
    const html = renderEntities([entity({})], undefined);
    expect(html).toContain('缺少 bayou 的地图定义');
  });
});
