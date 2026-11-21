import * as THREE from 'three';

export class HandTracker {
  constructor({ canvas, camera, physics, pickables, onGrab, onRelease, onMove, onStatus }) {
    this.canvas = canvas;
    this.camera = camera;
    this.physics = physics;
    this.pickables = pickables;
    this.onGrab = onGrab;
    this.onRelease = onRelease;
    this.onMove = onMove;
    this.onStatus = onStatus;
    this.video = document.createElement('video');
    this.video.setAttribute('playsinline', '');
    this.video.setAttribute('webkit-playsinline', '');
    this.video.muted = true;
    this.video.autoplay = true;
    this.video.width = 640;
    this.video.height = 480;
    this.stream = null;
    this.hands = null;
    this.active = false;
    this.starting = false;
    this.frameId = null;
    this.processing = false;
    this.lastFrameAt = 0;
    this.handPresent = false;
    this.grabbedObject = null;
    this.offset = new THREE.Vector3();
    this.plane = new THREE.Plane();
    this.planeNormal = new THREE.Vector3();
    this.hitPoint = new THREE.Vector3();
    this.targetPos = new THREE.Vector3();
    this.raycaster = new THREE.Raycaster();
  }

  _status(message) {
    this.onStatus?.(message);
  }

  _cameraError(error) {
    const name = error?.name || '';
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError' || name === 'SecurityError') {
      return 'Camera permission blocked. Allow camera access for this site in Chrome settings, then retry.';
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return 'No camera was found on this device.';
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return 'Camera is busy in another app or browser tab. Close other camera apps and retry.';
    }
    if (name === 'OverconstrainedError') {
      return 'This camera does not support the requested settings. Retry with default camera settings.';
    }
    if (!window.isSecureContext) {
      return 'Camera requires HTTPS. Deploy this site to GitHub Pages or another HTTPS host.';
    }
    return error?.message || 'Could not start the camera. Check browser permissions and retry.';
  }

  async start() {
    if (this.active) return true;
    if (this.starting) return false;
    this.starting = true;
    this._status('Requesting camera permission…');

    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        throw new Error('Camera requires a secure HTTPS website (or localhost).');
      }
      if (typeof window.Hands !== 'function') {
        throw new Error('MediaPipe Hands did not load. Check your internet connection and reload the page.');
      }

      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: 'user' },
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30, max: 30 }
        }
      });

      this.video.srcObject = this.stream;
      await this.video.play();

      this.hands = new window.Hands({
        locateFile: (file) => 'https://cdn.jsdelivr.net/npm/@mediapipe/hands/' + file
      });
      this.hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 0,
        minDetectionConfidence: 0.55,
        minTrackingConfidence: 0.5
      });
      this.hands.onResults((results) => this._onResults(results));

      this.active = true;
      this.handPresent = false;
      this._status('Camera ready • show one hand to the camera');
      this._scheduleFrame();
      return true;
    } catch (error) {
      console.warn('Hand tracking startup failed:', error);
      this.stop();
      this._status(this._cameraError(error));
      throw error;
    } finally {
      this.starting = false;
    }
  }

  _scheduleFrame() {
    if (!this.active || this.frameId !== null) return;
    this.frameId = requestAnimationFrame(async (now) => {
      this.frameId = null;
      if (!this.active || !this.hands || this.processing) return;
      if (now - this.lastFrameAt < 30) {
        this._scheduleFrame();
        return;
      }
      if (this.video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        this._scheduleFrame();
        return;
      }
      this.lastFrameAt = now;
      this.processing = true;
      try {
        await this.hands.send({ image: this.video });
      } catch (error) {
        console.warn('MediaPipe frame error:', error);
        this._status('Hand tracking paused. Check your connection and restart tracking.');
        this.stop();
      } finally {
        this.processing = false;
        this._scheduleFrame();
      }
    });
  }

  stop() {
    this.active = false;
    if (this.frameId !== null) cancelAnimationFrame(this.frameId);
    this.frameId = null;
    this.handPresent = false;
    if (this.grabbedObject) this._releaseHand();

    if (this.hands) {
      try { this.hands.close(); } catch (error) { console.warn(error); }
      this.hands = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    this.video.pause();
    this.video.srcObject = null;
    this._status('Hand tracking stopped');
  }

  _onResults(results) {
    const landmarks = results.multiHandLandmarks?.[0];
    if (!landmarks) {
      if (this.handPresent) this._status('Camera ready • no hand detected');
      this.handPresent = false;
      if (this.grabbedObject) this._releaseHand();
      return;
    }

    if (!this.handPresent) this._status('Hand detected • pinch thumb and index finger to grab');
    this.handPresent = true;
    this.currentHand = landmarks;

    const indexTip = landmarks[8];
    const thumbTip = landmarks[4];
    const x = 1 - indexTip.x;
    const y = indexTip.y;
    const z = indexTip.z || 0;
    const pinchDistance = Math.hypot(indexTip.x - thumbTip.x, indexTip.y - thumbTip.y);
    const isPinching = pinchDistance < 0.065;

    this._setRayFromScreen(x, y);
    if (isPinching && !this.grabbedObject) this._tryGrab();
    else if (!isPinching && this.grabbedObject) this._releaseHand();
    if (this.grabbedObject) this._updateGrab();
    this.onMove?.({ hand: landmarks, isPinching, x, y, z });
  }

  _setRayFromScreen(x, y) {
    this.raycaster.setFromCamera(new THREE.Vector2(x * 2 - 1, -(y * 2 - 1)), this.camera);
  }

  _tryGrab() {
    const intersections = this.raycaster.intersectObjects(this.pickables, true);
    if (!intersections.length) return;
    let root = intersections[0].object;
    while (root && root.parent && !this.pickables.includes(root)) root = root.parent;
    if (!root || !this.pickables.includes(root)) return;

    this.grabbedObject = root;
    const body = root.userData.physicsBody;
    if (body) {
      body.velocity.setZero();
      body.angularVelocity.setZero();
      body.type = 4;
      body.mass = 0;
      body.updateMassProperties();
      body.wakeUp();
    }
    this.camera.getWorldDirection(this.planeNormal);
    this.plane.setFromNormalAndCoplanarPoint(this.planeNormal, root.position);
    this.raycaster.ray.intersectPlane(this.plane, this.hitPoint);
    this.offset.copy(root.position).sub(this.hitPoint);
    this._status('Object grabbed • release pinch to drop');
    this.onGrab?.(root);
  }

  _updateGrab() {
    if (!this.grabbedObject || !this.currentHand) return;
    const indexTip = this.currentHand[8];
    this._setRayFromScreen(1 - indexTip.x, indexTip.y);
    if (this.raycaster.ray.intersectPlane(this.plane, this.hitPoint)) {
      this.targetPos.copy(this.hitPoint).add(this.offset);
      this.targetPos.y = Math.max(0.08, this.targetPos.y);
      this.grabbedObject.position.lerp(this.targetPos, 0.4);
      const body = this.grabbedObject.userData.physicsBody;
      if (body) {
        body.position.set(this.grabbedObject.position.x, this.grabbedObject.position.y, this.grabbedObject.position.z);
        body.quaternion.set(this.grabbedObject.quaternion.x, this.grabbedObject.quaternion.y, this.grabbedObject.quaternion.z, this.grabbedObject.quaternion.w);
        body.wakeUp();
      }
    }
  }

  _releaseHand() {
    if (!this.grabbedObject) return;
    const object = this.grabbedObject;
    const body = object.userData.physicsBody;
    if (body) {
      body.type = 1;
      body.mass = object.userData.type === 'planet' ? 1.2 : object.userData.type === 'creature' ? 0.8 : 0.4;
      body.updateMassProperties();
      this.physics?.syncBodyFromMesh?.(object);
      body.wakeUp();
    }
    this.grabbedObject = null;
    this.onRelease?.(object);
  }

  dispose() {
    this.stop();
  }
}
