import * as THREE from 'three';

export class PointerInteraction {
  constructor({ canvas, camera, scene, physics, pickables, onPick, onRelease }) {
    this.canvas = canvas;
    this.camera = camera;
    this.scene = scene;
    this.physics = physics;
    this.pickables = pickables;
    this.onPick = onPick;
    this.onRelease = onRelease;

    this.raycaster = new THREE.Raycaster();
    this.ndc = new THREE.Vector2();
    this.plane = new THREE.Plane();
    this.planeNormal = new THREE.Vector3();
    this.hitPoint = new THREE.Vector3();
    this.offset = new THREE.Vector3();
    this.targetPos = new THREE.Vector3();
    this.lastPos = new THREE.Vector3();
    this.velocity = new THREE.Vector3();

    this.active = false;
    this.dragObject = null;
    this.pointerId = null;

    this._onDown = this._onDown.bind(this);
    this._onMove = this._onMove.bind(this);
    this._onUp = this._onUp.bind(this);

    canvas.addEventListener('pointerdown', this._onDown);
    window.addEventListener('pointermove', this._onMove);
    window.addEventListener('pointerup', this._onUp);
    window.addEventListener('pointercancel', this._onUp);
  }

  _setFromEvent(event) {
    const rect = this.canvas.getBoundingClientRect();
    this.ndc.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.ndc.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.ndc, this.camera);
  }

  _pickRoot(object) {
    let o = object;
    while (o && o.parent && !this.pickables.includes(o)) o = o.parent;
    return this.pickables.includes(o) ? o : null;
  }

  _onDown(event) {
    if (this.active) return;
    // Keep mobile browsers from converting a drag gesture into page scrolling.
    if (event.cancelable) event.preventDefault();
    this._setFromEvent(event);
    const intersects = this.raycaster.intersectObjects(this.pickables, true);
    if (!intersects.length) return;

    const root = this._pickRoot(intersects[0].object);
    if (!root) return;

    this.active = true;
    this.dragObject = root;
    this.pointerId = event.pointerId;
    this.canvas.setPointerCapture?.(event.pointerId);

    this.camera.getWorldDirection(this.planeNormal);
    this.plane.setFromNormalAndCoplanarPoint(this.planeNormal, intersects[0].point);
    this.offset.copy(root.position).sub(intersects[0].point);
    this.lastPos.copy(root.position);
    this.velocity.set(0, 0, 0);

    const body = root.userData.physicsBody;
    if (body) {
      body.velocity.setZero();
      body.angularVelocity.setZero();
      body.wakeUp();
      // KINEMATIC bodies follow the user's pointer; STATIC bodies cannot be moved reliably.
      body.type = 4;
      body.mass = 0;
      body.updateMassProperties();
    }

    if (this.onPick) this.onPick(root);
  }

  _onMove(event) {
    if (!this.active || event.pointerId !== this.pointerId || !this.dragObject) return;
    if (event.cancelable) event.preventDefault();
    this._setFromEvent(event);
    if (this.raycaster.ray.intersectPlane(this.plane, this.hitPoint)) {
      this.targetPos.copy(this.hitPoint).add(this.offset);
      this.targetPos.y = Math.max(0.08, this.targetPos.y);
    }
  }

  _onUp(event) {
    if (!this.active || (this.pointerId !== null && event.pointerId !== this.pointerId)) return;
    if (this.dragObject) {
      const body = this.dragObject.userData.physicsBody;
      if (body) {
        body.type = 1;
        body.mass = this.dragObject.userData.type === 'planet' ? 1.2 : (this.dragObject.userData.type === 'creature' ? 0.8 : 0.4);
        body.updateMassProperties();
        this.physics.syncBodyFromMesh(this.dragObject);
        const v = this.velocity.clone().multiplyScalar(0.9);
        body.velocity.set(v.x, v.y, v.z);
        body.wakeUp();
      }
    }
    this.release();
  }

  update() {
    if (!this.active || !this.dragObject) return;
    const obj = this.dragObject;
    const prev = obj.position.clone();
    obj.position.lerp(this.targetPos, 0.35);
    this.velocity.copy(obj.position).sub(prev).multiplyScalar(60);
    this.physics.syncBodyFromMesh(obj);
    this.lastPos.copy(obj.position);
  }

  release() {
    const had = this.active;
    this.active = false;
    this.dragObject = null;
    this.pointerId = null;
    if (had && this.onRelease) this.onRelease();
  }

  dispose() {
    this.canvas.removeEventListener('pointerdown', this._onDown);
    window.removeEventListener('pointermove', this._onMove);
    window.removeEventListener('pointerup', this._onUp);
    window.removeEventListener('pointercancel', this._onUp);
  }
}
