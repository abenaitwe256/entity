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

ENTITY is one unified ecosystem with 14 permanent, interconnected divisions coordinated by central services. The complete authoritative register and identifiers are in [ENTITY_DIVISION_REGISTER.md](ENTITY_DIVISION_REGISTER.md). The table below summarizes the same full set; it does not add, remove, merge or rename divisions.

| Division | Primary responsibility |
|---|---|
| **ENTITY MIND** | Intelligence, reasoning and knowledge. |
| **ENTITY REALITY** | AR, VR, MR, 3D environments and human interaction. |
| **ENTITY HUMAN** | Biology, medicine, genetics, neuroscience and human regeneration. |
| **ENTITY SCIENCE** | Physics, mathematics, chemistry and scientific research. |
| **ENTITY ENGINEERING** | Engineering, robotics, materials and technological design. |
| **ENTITY SPACE** | Astronomy, spacecraft, orbital mechanics and space exploration. |
| **ENTITY PLANET** | Earth systems, climate, environment and ecosystems. |
| **ENTITY FUTURE** | Predictive modelling, emerging technologies and invention. |
| **ENTITY NANO** | Nanotechnology, nanoscale materials and molecular engineering. |
| **ENTITY QUANTUM** | Quantum science, quantum computing and quantum simulations. |
| **ENTITY REVERSE** | Reverse engineering of software, hardware and physical systems. |
| **ENTITY CODE** | Programming, software engineering, AI development and debugging. |
| **ENTITY EVOLVE** | Controlled continuous learning, evaluation and Owner-approved self-improvement. |
| **ENTITY CORE** | Central orchestration, identity, authorization, security and governance. |

### Division coordination
- ENTITY MIND acts as the central orchestration and user-interaction layer; it does not replace specialist expertise.
- Divisions collaborate on cross-disciplinary tasks. For example, ENTITY SPACE and ENTITY ENGINEERING can jointly develop a spacecraft concept, while ENTITY PLANET and ENTITY SCIENCE analyze Earth-observation data.
- Shared services provide identity, permissions, memory, audit logs, data provenance, research tools, simulation, and safety checks.
- A division may recommend or prepare an action, but real-world execution remains subject to the platform's autonomy policy, user permissions, and risk-based approval requirements.
- Specialist capabilities may evolve within the permanent register; the division set itself changes only through explicit governance review.

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


## ENTITY user ranks, access levels, and operational assignments

ENTITY uses an owner-governed, rank-based access-control system. Every human account must be explicitly authorized by the ENTITY Owner before access is granted. Rank defines the maximum authority a person may hold; actual permissions are further limited by division, assigned task, data classification, device/session trust, and risk policy. No rank automatically grants unrestricted access to every division or dataset.

### Authority hierarchy

| Rank | Role | Default authority and responsibility |
|---|---|---|
| **Rank 0 — OWNER** | ENTITY Owner (founder) | Sole root authority. Approves all user access, appoints/removes administrators and division directors, defines global policies, grants exceptional permissions, and can suspend any account or operation. |
| **Rank 1 — EXECUTIVE ADMINISTRATOR** | Owner-appointed senior administrator | Manages approved accounts, access requests, operational coordination, and platform administration within explicitly delegated limits. Cannot transfer ownership, override owner-only controls, or grant themselves higher privileges. |
| **Rank 2 — DIVISION DIRECTOR** | One director for an assigned ENTITY division | Leads only their assigned division, assigns its approved work, manages its team within delegated limits, and reports progress and risks to the Owner/authorized executive administrator. |
| **Rank 3 — DIVISION LEAD / SENIOR SPECIALIST** | Technical or operational lead | Supervises a defined team or specialist function, reviews work, and coordinates assigned tasks within the division and permissions granted. |
| **Rank 4 — OPERATOR / SPECIALIST** | Authorized task performer | Executes specific approved operational, technical, research, or device tasks. Access is limited to the tools, data, systems, and operations required for the assignment. |
| **Rank 5 — ANALYST / RESEARCHER** | Research and analysis contributor | Reads permitted datasets, performs approved analysis, prepares reports and recommendations, and cannot execute restricted operational actions unless separately authorized. |
| **Rank 6 — VIEWER / GUEST** | Limited-access user | Views only explicitly shared content or outputs. No administrative privileges and no access to restricted systems or private user data. |

### Individual task ownership

- Every operational task must have a named accountable person or approved service identity, a responsible division, a task description, permitted tools/data, scope, risk level, deadline or review point, and a defined completion condition.
- Use a task-assignment record with: task ID, assignee, assigning authority, division, required rank/permissions, resources, start/end time, approval state, execution status, evidence/output, and audit history.
- A person may hold different task permissions in different divisions, but only when explicitly authorized. Membership in one division does not imply access to another.
- Delegation must be explicit, scoped, and revocable. Temporary elevated access should expire automatically. Users cannot approve their own privilege escalation.
- High-impact, irreversible, safety-critical, medical, financial, biological, cyber, physical-device, robotics, or spacecraft actions require the appropriate additional approval gates regardless of rank. Rank does not bypass risk-based human approval.
- Automated agents and background services must use separate non-human identities with narrowly scoped credentials, explicit task permissions, execution limits, monitoring, and revocation. They do not inherit a human user's full rank.

### Access-control enforcement

- Implement role-based access control (RBAC) combined with attribute/task-based checks (ABAC): rank, division, task assignment, resource classification, action, environment, and risk must all be evaluated before access or execution.
- Apply least privilege and deny by default. Check authorization on the server for every protected operation; hiding a button in the interface is not security.
- Separate read, create, modify, approve, execute, administer, and revoke permissions. Sensitive operations should use separation of duties where practical.
- Require secure authentication, multi-factor authentication for owner and privileged accounts, session/device controls, protected recovery, and step-up authentication for critical actions.
- Maintain tamper-evident audit records for access grants, denials, role changes, task assignment, approvals, data access, exports, and operational actions.
- Plan an authenticated Owner dashboard for users, ranks, divisions, assigned tasks, sessions, approvals, exceptions, and audit history; this dashboard is not implemented. See [the dashboard architecture](ENTITY_OWNER_DASHBOARD.md).
- Support immediate suspension, credential/session revocation, emergency lockdown, and documented recovery procedures.
- Never store passwords or API secrets in source code or grant access through shared accounts.

### Ownership and governance rule

The designated Original Founder and Owner's identity and authority safeguards are described in [ENTITY governance](ENTITY_GOVERNANCE.md); the future dashboard boundary is in [ENTITY_OWNER_DASHBOARD.md](ENTITY_OWNER_DASHBOARD.md). The Owner identity is not inferred from public biographical details. The ENTITY Owner remains the final authority over who joins ENTITY and who may hold each rank. Executive administrators and division leaders may recommend candidates or request access changes, but may only approve or perform changes that the Owner has explicitly delegated. Ownership cannot be transferred or overridden by another user, division, or autonomous agent.

### Implementation requirement

This access model is a required platform foundation, not merely a documented interface. Implement the identity and authorization service before exposing sensitive divisions or real-world controls. Add automated tests for privilege escalation, cross-division access, expired assignments, revoked users, self-approval, unauthorized execution, and Owner account recovery. The current recovery policy fails closed and does not support account takeover or subject rebinding; see [ENTITY_OWNER_RECOVERY.md](ENTITY_OWNER_RECOVERY.md). Until enforcement is implemented and tested, the system must not claim that rank-based access control is active.
