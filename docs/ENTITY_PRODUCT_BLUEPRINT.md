## Product principles

1. Build real, testable capabilities—not visual-only buttons or simulated features presented as working.
2. Keep one central intelligence with specialist capabilities and shared, permissioned context.
3. Explain complex topics at simple, technical, and expert levels.
4. Cite current sources for research and distinguish established facts, estimates, simulations, and hypotheses.
5. Make permissions, privacy, user control, and data provenance visible.
6. Design for Android phones first, while keeping interfaces modular for later iOS and other devices.
7. Scale graphics and computation to device capability; preserve a usable experience on lower-end phones.

## Capability map

### 1. ENTITY Intelligence
- General reasoning, knowledge, planning, writing, tutoring, research, and problem solving.
- Conversation memory with user controls and scoped permissions.
- Clear explanations, worked examples, calculations, and uncertainty statements.
- Tool use for verified web research, computation, files, and approved device actions.

### 2. Specialist intelligence
- Aerospace and spacecraft engineering: mission requirements, preliminary architecture, propulsion comparisons, materials, structures, thermal systems, power, communications, navigation, life support, orbital mechanics, CAD-ready specifications, bills of materials, simulations, test plans, and risk analysis.
- Genetics and molecular biology: DNA/RNA, chromosomes, gene expression, proteins, mutations, genomics, inheritance, biotechnology, and gene editing.
- Medicine and pharmacology: educational explanations, diagnostics and laboratory science, mechanisms, pharmacokinetics, drug interactions, clinical literature, and research developments.
- Physics: mechanics, electromagnetism, thermodynamics, fluids, quantum physics, relativity, nuclear physics, and astrophysics.
- Mathematics: algebra, calculus, differential equations, linear algebra, statistics, numerical methods, geometry, and modelling.
- General engineering, materials science, robotics, computing, and emerging technologies.

Specialists should be coordinated by the central intelligence rather than implemented as isolated chatbots. High-stakes medical, biological, and engineering outputs require appropriate professional review and validation before real-world use.

### 3. ENTITY Reality
- Camera-based augmented reality with plane/surface detection and spatial anchors.
- Place and manipulate 3D characters, animals, vehicles, objects, and environments in the user's surroundings.
- Hand tracking and gestures: point, select, grab, move, resize, rotate, and release.
- Natural character movement, reactions, expressions, and context-aware interaction.
- Voice conversations with digital characters.
- Android-first implementation; evaluate ARCore/device support and graceful fallbacks.

### 4. ENTITY Voice
- Natural speech input and spoken responses.
- Optional wake phrase and explicit earbud-button activation.
- Supported background conversation through Android foreground services and visible notification.
- Bluetooth headset integration where Android and device APIs permit.
- Clear microphone state, mute/stop controls, battery safeguards, and user-controlled permissions.

Background microphone access must follow Android platform rules. Camera-based AR generally requires the app to be active. ENTITY must never secretly record or monitor the user.

### 5. ENTITY Control
- User-approved Android actions such as opening supported apps, media controls, reminders, and navigation intents.
- Use Android intents and supported APIs; accessibility access only when justified and explicitly enabled.
- Confirm sensitive or consequential actions. Never bypass device security or app protections.

### 6. ENTITY Projection
- User-authorized screen capture through Android MediaProjection.
- Floating virtual workspaces for supported images, documents, videos, webpages, and app content.
- Voice and gesture controls for moving, resizing, selecting, and navigating virtual panels.
- Convert compatible content into 3D representations when a reliable conversion path exists.

Protected media and secure app screens may block capture. Ordinary phones display AR content through the screen/camera; they do not create free-air holograms without specialized optical hardware.

### 7. ENTITY Human Intelligence
- Emotion-aware interaction using optional facial expression, voice tone, and conversational context; present these as uncertain signals, never definitive mind-reading.
- Connect compatible wearables and medical devices for supported measurements such as heart rate, oxygen saturation, ECG, blood pressure, temperature, sleep, activity, respiratory rate, and glucose where a compatible sensor provides it.
- Import consented laboratory results and clinical records where integrations permit.
- Anatomical visualizations and an evolving personal physiology model that labels measured, inferred, and simulated values.
- Trend summaries and carefully qualified alerts, not autonomous diagnosis or treatment.
- Strong consent, encryption, data minimization, provenance, pause, export, and deletion controls.

A phone camera alone cannot reveal all internal biological events in real time. Biological monitoring depends on validated compatible sensors and data sources.

### 8. ENTITY Global Sensing and Telemetry
- A global sensing and measurement capability that combines authorized satellite observations, Earth-observation products, weather and environmental stations, ocean and seismic networks, GNSS measurements, scientific instruments, IoT devices, and openly available digital telemetry.
- Observe and analyse measurable phenomena across Earth, near-Earth space, deep space, and connected digital infrastructure: location and movement where lawfully available, temperature, pressure, humidity, air and water quality, radiation, magnetic fields, seismic activity, ocean conditions, atmospheric composition, land use, vegetation, fires, storms, space weather, satellite status, orbital objects, network health, and other instrument-specific signals.
- Build a unified geospatial and temporal data layer with maps, timelines, live dashboards, alerts, historical comparisons, forecasts, and 3D globe/space visualizations.
- Fuse multiple data sources while preserving source attribution, timestamp, geographic coverage, resolution, calibration, uncertainty, update frequency, and confidence.
- Distinguish direct sensor measurements from satellite-derived estimates, model outputs, forecasts, interpolations, and AI-generated interpretations.
- Support user-connected sensors and approved APIs, public scientific datasets, licensed commercial feeds, and partner networks. Respect authentication, terms of use, privacy, cybersecurity, export controls, and local laws.
- Provide alerts and anomaly detection for events such as severe weather, environmental hazards, infrastructure changes, and space-weather disturbances, with human verification for consequential decisions.

**Scope and limits:** This is a global telemetry and sensor-fusion ambition—not literal omniscience or guaranteed access to every sensor, network, website, or private system. ENTITY can only measure or analyse phenomena covered by available instruments and authorized data feeds. Satellite imagery has revisit, resolution, cloud-cover, latency, and licensing limits; internet telemetry is limited to systems that expose data or grant access. It must never conduct covert tracking, unauthorized network probing, or surveillance of individuals.

### 9. ENTITY Scientific Lab
- Reproducible calculations, simulations, graphs, diagrams, technical reports, 3D models, CAD-ready outputs, and bills of materials.
- Show assumptions, equations, units, source references, validation checks, and uncertainty.
- Engineering simulation results must be labelled as preliminary until validated against appropriate tools, standards, and physical testing.

### 10. ENTITY World
- An original high-definition interactive 3D world with believable environments, characters, physics, and interactions.
- Build original assets and environments; do not copy protected game maps, characters, or assets.
- Scale rendering quality, shadows, assets, and simulation load for mobile hardware.
- Future extensions may include vehicles, traffic, missions, interiors, and larger streamed environments.


## ENTITY division structure

ENTITY is organized into eight interconnected divisions coordinated by one central intelligence. Each division owns a specialist responsibility while sharing permissioned tools, context, data provenance, and safety policies.

| Division | Primary responsibility |
|---|---|
| **ENTITY MIND** | Intelligence, reasoning, knowledge, planning, memory, research coordination, and communication. |
| **ENTITY REALITY** | Augmented reality, immersive 3D worlds, spatial computing, digital characters, projection, and human interaction. |
| **ENTITY HUMAN** | Human biology, medicine, genetics, physiology, neuroscience, neural technology, and consent-based health intelligence. |
| **ENTITY SCIENCE** | Physics, mathematics, chemistry, astronomy, scientific research, modelling, and reproducible simulations. |
| **ENTITY ENGINEERING** | Inventions, aerospace and general engineering, robotics, automation, materials science, and prototype development. |
| **ENTITY SPACE** | Satellites, spacecraft, orbital systems, space missions, astronomy data, and authorized space-system interaction. |
| **ENTITY PLANET** | Earth intelligence, global sensing, environmental monitoring, geospatial data, climate, oceans, and disaster intelligence. |
| **ENTITY FUTURE** | Prediction, discovery, scenario modelling, autonomous innovation, and long-term technology exploration. |

### Division coordination
- ENTITY MIND acts as the central orchestration and user-interaction layer; it does not replace specialist expertise.
- Divisions collaborate on cross-disciplinary tasks. For example, ENTITY SPACE and ENTITY ENGINEERING can jointly develop a spacecraft concept, while ENTITY PLANET and ENTITY SCIENCE analyze Earth-observation data.
- Shared services provide identity, permissions, memory, audit logs, data provenance, research tools, simulation, and safety checks.
- A division may recommend or prepare an action, but real-world execution remains subject to the platform's autonomy policy, user permissions, and risk-based approval requirements.
- The division structure is modular: new divisions and specialist capabilities may be added without redesigning the entire system.

## Proposed technical architecture

- **Android application layer:** Kotlin/Jetpack Compose or an equivalent maintained native Android stack for permissions, foreground voice service, Bluetooth, intents, MediaProjection, lifecycle, and device integrations.
- **3D and AR layer:** Three.js for the current web prototype and rapid iteration; evaluate native ARCore integration for robust Android AR and spatial tracking.
- **AI backend:** secure API service for central orchestration, specialist routing, tool access, retrieval, and permission-scoped memory.
- **Scientific compute:** isolated, testable computation services for numerical work and simulations; use established domain libraries where possible.
- **Data layer:** secure database and object storage with explicit access controls, auditability, retention rules, and encryption.
- **Global telemetry layer:** geospatial/time-series ingestion, satellite and scientific data connectors, sensor/API adapters, provenance metadata, stream processing, alerting, and role-based access controls.
- **Client interface:** modular mobile-first UI with clear states for voice, AR, projection, research, and device permissions.

No API keys, credentials, or private health data should be committed to the repository.

## Delivery roadmap

### Phase 0 — Foundation and safety
- Confirm product requirements and architecture.
- Establish repository structure, build/test workflow, environment configuration, and coding standards.
- Define permissions, threat model, privacy model, and data classifications.

### Phase 1 — ENTITY Intelligence
- Build the central assistant interface and backend contract.
- Add specialist routing, research citations, calculation tools, and explainability.
- Add user-controlled memory and secure session handling.

### Phase 2 — ENTITY Voice and Control
- Native Android app shell.
- Foreground voice service, speech recognition/synthesis, headset controls, and supported actions.
- Permission UX, confirmations, and battery/lifecycle testing.

### Phase 3 — ENTITY Reality
- AR camera session, plane detection, spatial placement, and 3D asset pipeline.
- Gesture recognition and object manipulation.
- Character interaction and voice dialogue.

### Phase 4 — ENTITY Projection
- MediaProjection consent flow and virtual workspace.
- Supported content panels and gesture/voice controls.
- Respect secure-screen and protected-content restrictions.

### Phase 5 — ENTITY Scientific Lab and Human Intelligence
- Reproducible scientific tools and engineering workflows.
- Compatible wearable/device integrations and consented health-data ingestion.
- Global sensing connectors, geospatial/time-series processing, source-quality checks, and live telemetry dashboards.
- Biological and Earth/space visualizations, trends, provenance, and safety review.

### Phase 6 — ENTITY World and ecosystem integration
- Expand the original 3D world, physics, characters, and mobile performance.
- Connect voice, intelligence, AR, projection, scientific tools, and device actions into one experience.
- Run end-to-end reliability, security, accessibility, and device-compatibility testing.

### Phase 7 — ENTITY Autonomous Operations, Robotics, and Cosmic Research
- Implement permission-scoped task planning, policy checks, execution verification, audit trails, and human approval gates.
- Integrate simulated robotics first, then compatible physical platforms in controlled test environments.
- Add safe robotics adapters, emergency-stop behavior, hardware health checks, and operator handoff.
- Integrate astronomy archives, telescope/scientific datasets, and authorized mission telemetry with provenance and uncertainty.
- Build cosmic-scale visualization and modelling workflows while documenting observational and physical limits.

## Current repository baseline

The existing repository is an early Three.js/Cannon-es prototype with pointer/touch interaction, browser voice hooks, MediaPipe hand tracking, camera passthrough, and a Pepper's Ghost display mode.

- PR #2 (mobile camera/hand/voice improvements) is merged into main, but physical Android camera and microphone behavior still needs verification.
- PR #3 (HD original open-world prototype) is open and unmerged. It requires build and physical-device testing before merge.
- The current browser prototype is not yet a native Android companion and does not implement the full ENTITY platform.

## Definition of done

A feature is not complete merely because a button or screen exists. Each capability must include:
- Working implementation and clear permission handling.
- Loading, success, failure, and recovery states.
- Automated tests where practical and documented manual device tests.
- Performance and accessibility checks appropriate to target devices.
- Security and privacy review for sensitive capabilities.
- Documentation of limitations and supported devices.
