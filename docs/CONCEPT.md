# Concept & Design Notes

This project prototypes a **realtime holographic/XR social interface** where users physically interact with virtual miniature worlds, planets, and creatures.

## Core principles

- **Physicality first**: interactions should feel tactile. Objects are physics-driven (momentum, bounce, weight) rather than purely scripted.
- **Device-mediated visibility**: virtual content is visible only through a viewing device:
  - Phone/screen AR-style view (camera passthrough + 3D overlay)
  - Holographic presentation (Pepper's Ghost pyramid reflector over a screen)
- **Multimodal input**: touch/hand gestures and voice commands.
- **Social by design**: architecture should extend to shared spaces, co-presence, and proximity voice.

## Interaction model (prototype scope)

- **Grab/move/throw**: pointer/touch drag maps to physics body manipulation and imparts velocity on release.
- **Voice commands**: `grow`, `shrink`, `spin`, `jump`, `reset`, `planet`, `creature`, `come here`.
- **Creatures/worlds**: miniature planet + creature props demonstrate scale, idle motion, and direct manipulation.

## Planned extensions

- **Hand tracking**: MediaPipe Hands for mid-air pinch/grab/pet gestures.
- **Natural creature behavior**: blending autonomous idle/react states with physics responses.
- **Spatial audio**: HRTF-based binaural rendering, distance attenuation, occlusion, proximity voice.
- **Multi-user**: shared state (ownership, locks), avatars/hands, spatial voice, world visiting.
- **Assets**: glTF models, animations, and richer planet surfaces.

## Key risks to validate early

- **Latency & responsiveness** of grab interactions.
- **Scale readability** for miniature worlds on small screens.
- **Comfort** (motion, audio density, visual clutter).
- **Tracking robustness** (lighting, occlusion of hands).
