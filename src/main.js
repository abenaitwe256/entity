import { World } from './scene/world.js';
import { PhysicsWorld } from './physics/physicsWorld.js';
import { PointerInteraction } from './interaction/pointer.js';
import { HandTracker } from './interaction/handTracking.js';
import { VoiceController } from './interaction/voice.js';
import { HologramRenderer } from './hologram/hologramRenderer.js';
import { initUI } from './ui/ui.js';
import { AudioManager } from './audio/audioManager.js';

const canvas = document.getElementById('app');
const statusEl = document.getElementById('status');
const cameraVideo = document.getElementById('camera-bg');

const state = {
  mode: 'screen', // 'screen' | 'hologram'
  cameraPassthrough: false,
  voiceActive: false,
  selected: null,
};

function setStatus(text) {
  statusEl.textContent = text;
}

const physics = new PhysicsWorld();
const world = new World(canvas, physics);
const hologram = new HologramRenderer(world.renderer, world.scene, world.camera);
const audio = new AudioManager(world.camera);

const pointer = new PointerInteraction({
  canvas,
  camera: world.camera,
  scene: world.scene,
  physics,
  pickables: world.pickables,
  onPick: (obj) => {
    state.selected = obj;
    audio.playGrab(obj?.userData?.name || 'object');
    setStatus(`Grabbed ${obj?.userData?.label || 'object'} • ${state.mode} mode`);
  },
  onRelease: () => {
    setStatus(`${state.mode === 'hologram' ? 'Hologram' : 'Screen'} mode • drag objects • try voice`);
  },
});

const voice = new VoiceController({
  onCommand: (cmd) => handleVoiceCommand(cmd),
  onStatus: (msg) => setStatus(msg),
});

const handTracker = new HandTracker({
  canvas,
  camera: world.camera,
  physics,
  pickables: world.pickables,
  onGrab: (obj) => {
    state.selected = obj;
    audio.playGrab(obj?.userData?.name || 'object');
    setStatus(`Hand grabbed ${obj?.userData?.label || 'object'} • ${state.mode} mode`);
  },
  onRelease: () => {
    setStatus(`${state.mode === 'hologram' ? 'Hologram' : 'Screen'} mode • pinch to grab`);
  },
  onStatus: (message) => setStatus(message),
});

const handButton = document.getElementById('btn-hand');
async function toggleHandTracking() {
  if (handTracker.active) {
    handTracker.stop();
    handButton?.classList.remove('active');
    handButton?.setAttribute('aria-pressed', 'false');
    if (handButton) handButton.textContent = 'Hand tracking';
    return;
  }
  if (handTracker.starting) return;
  try {
    await handTracker.start();
    handButton?.classList.add('active');
    handButton?.setAttribute('aria-pressed', 'true');
    if (handButton) handButton.textContent = 'Stop hands';
  } catch (error) {
    handButton?.classList.remove('active');
    handButton?.setAttribute('aria-pressed', 'false');
    if (handButton) handButton.textContent = 'Retry hands';
    console.warn(error);
  }
}
handButton?.addEventListener('click', toggleHandTracking);

function handleVoiceCommand(cmd) {
  const target = state.selected || world.getDefaultTarget();
  const label = target?.userData?.label || 'object';
  switch (cmd.type) {
    case 'grow':
      world.scaleObject(target, 1.2);
      setStatus(`Voice: grow ${label}`);
      break;
    case 'shrink':
      world.scaleObject(target, 0.83);
      setStatus(`Voice: shrink ${label}`);
      break;
    case 'spin':
      world.spinObject(target);
      setStatus(`Voice: spin ${label}`);
      break;
    case 'jump':
      world.jumpObject(target);
      audio.playBoop();
      setStatus(`Voice: jump ${label}`);
      break;
    case 'reset':
      resetScene();
      setStatus('Voice: reset scene');
      break;
    case 'selectPlanet':
      state.selected = world.planetGroup;
      setStatus('Voice: selected planet');
      break;
    case 'selectCreature':
      state.selected = world.creature;
      setStatus('Voice: selected creature');
      break;
    case 'comeHere':
      world.pullTowardCamera(target, world.camera);
      setStatus(`Voice: come here ${label}`);
      break;
    default:
      setStatus(`Voice heard: "${cmd.raw || ''}"`);
  }
}

async function setCameraPassthrough(on) {
  state.cameraPassthrough = on;
  document.body.classList.toggle('camera-on', on);
  if (on) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      cameraVideo.srcObject = stream;
      await cameraVideo.play().catch(() => {});
      setStatus('Camera passthrough on (screen mode)');
    } catch (err) {
      console.warn('Camera error', err);
      state.cameraPassthrough = false;
      document.body.classList.toggle('camera-on', false);
      setStatus('Camera permission denied/unavailable');
      ui.setCameraActive(false);
    }
  } else {
    const stream = cameraVideo.srcObject;
    if (stream && stream.getTracks) stream.getTracks().forEach(t => t.stop());
    cameraVideo.srcObject = null;
    setStatus('Camera passthrough off');
  }
}

function setMode(mode) {
  state.mode = mode;
  document.body.classList.toggle('hologram', mode === 'hologram');
  setStatus(`${mode === 'hologram' ? 'Hologram' : 'Screen'} mode • drag objects • try voice`);
}

function toggleVoice(on) {
  state.voiceActive = on;
  if (on) {
    const started = voice.start();
    if (!started) state.voiceActive = false;
    ui?.setVoiceActive(state.voiceActive);
  } else {
    voice.stop();
    ui?.setVoiceActive(false);
  }
}

function resetScene() {
  handTracker.stop();
  handButton?.classList.remove('active');
  handButton?.setAttribute('aria-pressed', 'false');
  if (handButton) handButton.textContent = 'Hand tracking';
  pointer.release();
  world.reset();
  physics.reset();
  state.selected = null;
}

const ui = initUI({
  onModeChange: setMode,
  onCameraToggle: setCameraPassthrough,
  onVoiceToggle: toggleVoice,
  onReset: resetScene,
});

// Resize handling
function onResize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  world.resize(w, h);
  hologram.resize(w, h);
}
window.addEventListener('resize', onResize);
onResize();

// Animation loop
let last = performance.now();
function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min((now - last) / 1000, 0.05);
  last = now;

  world.update(dt);
  physics.step(dt);
  physics.syncMeshes();
  pointer.update();
  audio.update();

  if (state.mode === 'hologram') {
    hologram.render();
  } else {
    world.render();
  }
}
requestAnimationFrame(animate);

// Prime audio on first gesture (browser autoplay policies)
window.addEventListener('pointerdown', () => audio.resume(), { once: true });

// Keyboard shortcut for voice
window.addEventListener('keydown', (e) => {
  if (e.key.toLowerCase() === 'v') ui.toggleVoice();
  if (e.key.toLowerCase() === 'r') resetScene();
});
