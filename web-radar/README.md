# Hunt Web Radar

Minimal React/Vite radar for Hunt: Showdown. It connects to a local WebSocket
endpoint, shows the radar image for the current map id, and draws unified
player/boss entities on top. There is no relay, login, replay, bomb timer, or
equipment UI.

## Build and verify

Requires Node.js 20.19+ (or 22.12+).

```bash
npm ci
npm test
npm run build
node scripts/validate-bundle.mjs dist
```

`dist/` is the static root. Vite copies `public/maps/` to `dist/maps/` during
the build. The validator checks every manifest image and enforces map-relative
PNG paths.

## Endpoints

- Page and assets are loaded from the current HTTP(S) origin.
- Snapshots arrive over `ws(s)://<current-host>/api/v1/stream`.
- The map catalogue is fetched from `/maps/manifest.json`.

## WebSocket v1

```ts
type ServerMessage =
  | { v: 1; type: 'hello'; serverTimeMs: number; updateHz?: number }
  | { v: 1; type: 'snapshot'; seq: number; capturedAtMs: number;
      map: { id: string }; entities: Entity[] }
  | { v: 1; type: 'error'; code: string; message: string };
```

Entity is a single structure shared by players and bosses; the `type` field
distinguishes them:

```ts
interface Entity {
  id: string;
  type: 'LocalPlayer' | 'FriendlyPlayer' | 'EnemyPlayer' | 'DeadPlayer'
    | 'Assassin' | 'Butcher' | 'Spider' | 'Scrapbeak' | 'Rotjaw' | 'Hellborn'
    | 'Other';
  position: { x: number; y: number; z: number } | null;
}
```

The exact TypeScript contract and runtime guards are in `src/types/protocol.ts`.

## Map manifest v1

```json
{
  "version": 1,
  "maps": [
    {
      "id": "bayou",
      "name": "Stillwater Bayou",
      "origin": { "x": -1000, "y": 1000 },
      "scale": 2.0,
      "image": "/maps/bayou/radar.png"
    }
  ]
}
```

World positions are normalized with:

```text
x = (world.x - origin.x) / (scale * 1024)
y = (origin.y - world.y) / (scale * 1024)
```

If `image` is absent, the UI falls back to `/maps/<id>/radar.png`.
