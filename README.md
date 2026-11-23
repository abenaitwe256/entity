# ENTITY (Prototype)

> Formerly **Holo Miniature World**. The product vision, divisions, roadmap and access-control model are in [`docs/ENTITY_PRODUCT_BLUEPRINT.md`](docs/ENTITY_PRODUCT_BLUEPRINT.md). The repository contains an early XR prototype and a separate identity/authorization service foundation. The browser prototype is not yet connected to that service.

Open-source prototype for a realtime XR/social interface where users physically interact with virtual miniature worlds, planets, and creatures.

## Concept

- **Miniature worlds**: summon, scale, and manipulate planets and animals in a shared tabletop-scale space.
- **Touch interaction**: grab, move, throw, and pet objects using hand tracking (MediaPipe) or pointer/touch input.
- **Voice interaction**: issue natural commands like "grow", "shrink", "spin", "jump", and "come here".
- **Natural motion**: physics-driven rigid bodies give objects momentum, bounce, and weight.
- **Holographic presentation**: virtual content is intended to be viewed only through a device:
  - **Phone/Screen mode**: interactive 3D view (optionally with camera passthrough background).
  - **Hologram mode**: Pepper's Ghost 4-quadrant rendering for use with a pyramid reflector.
- **Social-ready architecture**: designed to extend toward multi-user presence, shared ownership, and spatial voice.

## Project status

This repository contains an early single-user prototype scaffold focused on core interaction feel:

- Three.js rendering + Cannon-es physics
- Pointer/touch grab-and-drag with physics impulses
- Voice command hooks via Web Speech API
- Pepper's Ghost hologram viewport mode
- Camera passthrough toggle for phone-screen presentation

Implemented hand tracking for mid-air "touch" using MediaPipe (`src/interaction/handTracking.js`).
- Multi-user sync (WebRTC/Yjs or Colyseus/LiveKit data)
- Spatial/proximity voice
- Richer creature behaviors and assets (glTF)

## Getting started

### Option A: Quick run (no build, CDN imports)
Serve the folder with any static HTTP server (camera/mic permissions require a secure context; `localhost` is fine):

```bash
# Python
python -m http.server 5173

# or Node
npx serve .
```

Then open `http://localhost:5173`.

> Note: `index.html` uses an import map pointing to CDN modules for Three.js and Cannon-es so it can run without installing dependencies.

### Option B: Vite dev server

```bash
npm install
npm run dev
```

## Controls

- **Mouse/Touch:** click/tap and drag objects to grab and move them.
- **Voice (button or `V`):** say commands such as *grow*, *shrink*, *spin*, *jump*, *reset*, *planet*, *creature*.
- **View modes:** toggle Screen / Hologram (Pepper's Ghost).
- **Camera passthrough:** toggle device camera background in screen mode (permission required).

## Hologram (Pepper's Ghost) mode

1. Switch to **Hologram** mode.
2. Place a clear acrylic pyramid reflector on the phone/tablet screen (open designs can be added under `hologram/`).
3. View the reflected miniature world from the side of the pyramid.

The software renders four views; physical pyramid dimensions and calibration affect perceived alignment.

## Repository layout

```text
.
├─ index.html
├─ src/
│  ├─ main.js
│  ├─ scene/          # world, objects, lighting
│  ├─ physics/        # physics world + body sync
│  ├─ interaction/    # pointer/touch, hand tracking, voice
│  ├─ audio/          # spatial audio hooks
│  └─ ui/             # HUD/controls
├─ assets/            # models, textures (placeholders)
├─ backend/
│  └─ auth-service/   # OIDC identity and server-side authorization foundation
├─ docs/              # design notes
└─ hologram/          # (planned) pyramid templates/calibration
```

## Authentication service foundation

The standalone Python API under [backend/auth-service](backend/auth-service/README.md) now has server-derived resource policy, one-time independent approvals, Owner/Rank 1 two-person administration, revocable sessions and an Alembic migration path. Automated tests cover the main authorization boundaries. The browser remains a static prototype with no sign-in flow or authoritative product backend, so the service is **not production-ready** and the UI must not be treated as authenticated. See the [browser integration plan](docs/ENTITY_AUTH_BROWSER_INTEGRATION.md) and the service's remaining deployment blockers.

## Hand tracking setup

Hand tracking starts only when you tap the **Hand tracking** button. Use HTTPS (or `localhost` during development), allow camera access, show one hand to the front camera, and pinch your thumb and index finger while pointing at a pickable object. The status line reports camera permission, camera readiness, and hand detection. Tap **Stop hands** to release the camera.

MediaPipe Hands and Camera Utils are loaded from jsDelivr in `index.html`.

## Open-source stack (current/proposed)

- **Rendering:** Three.js (MIT)
- **Physics:** cannon-es (MIT)
- **Hand tracking:** MediaPipe Hands (Apache-2.0)
- **Voice:** Web Speech API (browser) now; Whisper.cpp / Vosk for offline/on-device later
- **Multi-user (planned):** Yjs + WebRTC or LiveKit

## Design principles

- Objects should feel tactile and responsive (physics-first interactions).
- Latency matters: grabbing/moving must feel immediate; networked ownership comes later.
- Scale clarity: miniature worlds need readable silhouettes, lighting, and audio cues.
- Device-only visibility: virtual content is presented through screen/holographic optics, not naked-eye projection.

## License

MIT — see `LICENSE`.
