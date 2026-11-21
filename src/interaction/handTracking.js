import * as THREE from 'three';

export class HandTracker {
  constructor({ canvas, camera, physics, pickables, onGrab, onRelease, onMove }) {
    this.canvas = canvas;
    this.camera = camera;
    this.physics = physics;
    this.pickables = pickables;
    this.onGrab = onGrab;
    this.onRelease = onRelease;
    this.onMove = onMove;
    this.video = document.createElement('video');
    this.video.setAttribute('playsinline', '');
    this.video.muted = true;
    this.video.width = 640;
    this.video.height = 480;
    this.hands = null;
    this.cameraHelper = null;
    this.active = false;
    this.starting = false;
    this.currentHand = null;
    this.grabbedObject = null;
    this.cameraReady = null;
    this.offset = new THREE.Vector3();
    this.plane = new THREE.Plane();
    this.planeNormal = new THREE.Vector3();
    this.hitPoint = new THREE.Vector3();
    this.targetPos = new THREE.Vector3();
    this.raycaster = new THREE.Raycaster();
  }

  async _initCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Camera access requires HTTPS (or localhost) and a supported browser.');
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 },
      audio: false
    });
    this.video.srcObject = stream;
    await this.video.play();
  }

  async start() {
    if (this.active || this.starting) return;
    this.starting = true;
    try {
      this.cameraReady ??= this._initCamera();
      await this.cameraReady;
      if (typeof window.Hands !== 'function' || typeof window.Camera !== 'function') {
        throw new Error('MediaPipe scripts are missing. Load hands.js and camera_utils.js in index.html.');
      }
      this.hands = new window.Hands({
        locateFile: (file) => 'https://cdn.jsdelivr.net/npm/@mediapipe/hands/' + file
      });
      this.hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.7,
        minTrackingConfidence: 0.6
      });
      this.hands.onResults((results) => this._onResults(results));
      this.cameraHelper = new window.Camera(this.video, {
        onFrame: async () => {
          if (this.active && this.hands) await this.hands.send({ image: this.video });
        },
        width: 640,
        height: 480
      });
      this.active = true;
      await this.cameraHelper.start();
    } catch (error) {
      this.active = false;
      this.cameraReady = null;
      console.warn('Unable to start hand tracking:', error);
      this.stop();
      throw error;
    } finally {
      this.starting = false;
    }
  }

  stop() {
    this.active = false;
    this.currentHand = null;
    if (this.grabbedObject) this._releaseHand();
    if (this.cameraHelper?.stop) this.cameraHelper.stop();
    this.cameraHelper = null;
    if (this.hands) {
      this.hands.close();
      this.hands = null;
    }
    const stream = this.video.srcObject;
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      this.video.srcObject = null;
    }
    this.cameraReady = null;
  }

  _onResults(results) {
    const landmarks = results.multiHandLandmarks?.[0];
    if (!landmarks) {
      if (this.grabbedObject) this._releaseHand();
      this.currentHand = null;
      return;
    }
    this.currentHand = landmarks;
    const indexTip = landmarks[8];
    const thumbTip = landmarks[4];
    const x = 1 - indexTip.x;
    const y = indexTip.y;
    const z = indexTip.z || 0;
    const pinchDistance = Math.hypot(indexTip.x - thumbTip.x, indexTip.y - thumbTip.y);
    const isPinching = pinchDistance < 0.06;
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
