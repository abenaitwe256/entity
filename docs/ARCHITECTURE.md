# Architecture Overview

## High-level modules

```text
src/
  main.js            # app bootstrap, loop, wiring
  scene/             # Three.js scene, camera, lights, objects
  physics/           # Cannon-es world, body creation, sync/reset
  interaction/       # pointer/touch grabbing, (future) hand tracking, voice
  audio/             # audio feedback + (future) spatialization/listener sync
  hologram/          # Pepper's Ghost 4-quadrant renderer
  ui/                # HUD controls and state toggles
```

## Runtime data flow

1. Input (pointer/voice/UI) produces intents: select, drag, scale, impulse, mode change.
2. Interaction layer updates object transforms or applies physics impulses.
3. Physics step advances simulation (cannon-es) and syncs dynamic bodies back to Three.js meshes.
4. Scene update applies idle/ambient animations (planet rotation, creature bob, etc.).
5. Render outputs either:
   - Single camera view (screen mode), or
   - Four rotated views (Pepper's Ghost hologram mode).
6. Audio provides feedback cues (currently simple beeps; future: spatialized sources + proximity voice).

## Object model

- **Visual**: Three.js Group/Mesh objects in `scene/world.js`.
- **Physical**: Cannon-es bodies registered in `physics/physicsWorld.js` and linked via `mesh.userData.physicsBody`.
- **Interaction**: pickable roots listed in `world.pickables`; pointer raycasts resolve to these roots.

## Visibility modes

- **Screen mode**: standard render to canvas; optional camera video background (`<video>` behind canvas) to simulate passthrough.
- **Hologram mode**: `HologramRenderer` renders the scene into four quadrants with camera orbits/roll so a Pepper's Ghost pyramid reflector can form a floating image.

## Future networking & social layer (planned)

- **Sync**: WebRTC + Yjs/CRDT or authoritative server for object transforms and ownership.
- **Presence**: avatars/hands, gaze/attention cues, proximity voice.
- **Ownership model**: grab-to-own with soft locks; host/authority for conflict resolution.
- **Persistence**: serialized world state (object placements, scales, user spaces).

## Open-source stack direction

- **Rendering**: Three.js (MIT) / WebXR-capable path
- **Physics**: cannon-es (MIT) now; Rapier as optional upgrade
- **Hand tracking**: MediaPipe Hands (Apache-2.0)
- **Voice**: Web Speech API now; Whisper.cpp / Vosk for offline
- **Networking/voice**: WebRTC, Yjs, LiveKit components as needed
- **Hologram optics**: Pepper's Ghost (screen + pyramid) and optional OST headsets (e.g. HoloKit-style) driven by the same scene
