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
backend/
  auth-service/      # separate Python OIDC identity and authorization API
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


## Identity and authorization foundation

`backend/auth-service/` is a separate backend service, not part of the static XR client runtime. It validates provider-issued JWT access tokens, resolves provisioned identities from PostgreSQL, tracks and revokes API-token sessions, and evaluates server-side rank, division, task, resource, risk, and approval context. The provider remains responsible for passwords, MFA enrollment, trusted-device policy, and owner account recovery.

The current browser prototype remains single-user and has no account or token flow. Sensitive product handlers must call the server-side policy using resource classification and risk values loaded from trusted backend state. A client-supplied policy check is not an authorization boundary. The service must be configured and tested before any sensitive division or real-world control is exposed.


## Authentication and authorization status

The current XR code is static and does not authenticate users or call the Python auth service. The backend foundation verifies OIDC tokens, checks revocable API sessions and evaluates policy using resource metadata stored server-side. A dedicated trusted workload identity must publish that metadata; client requests cannot choose division, resource owner, classification or risk.

Administrative mutations require an Owner with recent MFA, an independent Rank 1 reviewer, and exact payload-bound one-time approval. High/critical-risk or highly restricted access, and execute/administer/revoke actions, require a scoped task, recent MFA and an independent eligible approver. These service routes are covered by automated regression tests. The service also has a narrow metadata-reference read handler over the trusted resource-policy record; it does not read product content or cause external effects. Future domain handlers must load canonical product state, re-check authorization, consume approval, perform the protected effect and audit it in one secure transaction.

The service is not production-ready. No identity provider, resource registry or deployment is configured. Provider-specific claim mapping, operational monitoring, secret rotation, audit anchoring, recovery drills, and the browser integration remain incomplete. See [the browser integration plan](ENTITY_AUTH_BROWSER_INTEGRATION.md) and [service status](../backend/auth-service/README.md).


## Original Owner identity boundary

ENTITY governance designates Abenaitwe Dickson, born in Uganda, as the Original Founder and Owner with the highest governing Owner authority. Those descriptors are governance documentation only; they are not authentication factors or recovery evidence.

The auth service binds the configured OIDC issuer and pinned subject to one generated, immutable internal UUID and one exact Rank 0 account. OIDC token verification establishes the authenticated subject; controlled out-of-band identity proofing establishes whether that subject belongs to the designated human. Authorization then independently requires the bound account, required MFA/step-up, scoped policy, any independent approval and audit. There is no hardcoded Owner password, account transfer endpoint or alternate recovery identity. See [ENTITY governance](ENTITY_GOVERNANCE.md), [Owner recovery](ENTITY_OWNER_RECOVERY.md), and [the dashboard plan](ENTITY_OWNER_DASHBOARD.md).

The Owner bootstrap is an operator-run, replay-guarded transaction that requires verified tokens and fresh MFA for both the pinned Owner and pinned independent reviewer. The database migration protects the anchor and bound user with immutable PostgreSQL triggers. Recovery keeps the same issuer and subject; if they cannot be recovered, Owner-only actions remain unavailable. Live provider identity proofing, a recovery drill, runtime/migration database role separation and protection against a fully privileged database operator remain unvalidated.

ENTITY uses all 14 divisions listed in [the consolidated division register](ENTITY_DIVISION_REGISTER.md). The auth policy recognizes the same 14 lowercase identifiers; the former eight-division policy/blueprint set was incomplete.
