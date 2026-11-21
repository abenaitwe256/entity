import * as CANNON from 'cannon-es';
import * as THREE from 'three';

export class PhysicsWorld {
  constructor() {
    this.world = new CANNON.World({
      gravity: new CANNON.Vec3(0, -9.82, 0),
    });
    this.world.broadphase = new CANNON.NaiveBroadphase();
    this.world.solver.iterations = 10;
    this.world.allowSleep = true;

    const defaultMat = new CANNON.Material('default');
    this.defaultMat = defaultMat;
    const contact = new CANNON.ContactMaterial(defaultMat, defaultMat, {
      friction: 0.4,
      restitution: 0.25,
    });
    this.world.defaultContactMaterial = contact;

    this.bodies = new Map();
    this._tmpQuat = new THREE.Quaternion();
  }

  addBox(mesh, { mass = 1, size = null, kinematic = false } = {}) {
    const box = new THREE.Box3().setFromObject(mesh);
    const dims = new THREE.Vector3();
    box.getSize(dims);
    const half = (size ? new THREE.Vector3(...size) : dims).multiplyScalar(0.5);
    const shape = new CANNON.Box(new CANNON.Vec3(Math.max(0.01, half.x), Math.max(0.01, half.y), Math.max(0.01, half.z)));
    return this._addBody(mesh, shape, mass, kinematic);
  }

  addSphere(mesh, { mass = 1, radius = null, kinematic = false } = {}) {
    let r = radius;
    if (r == null) {
      const box = new THREE.Box3().setFromObject(mesh);
      const size = new THREE.Vector3();
      box.getSize(size);
      r = Math.max(size.x, size.y, size.z) * 0.5;
    }
    const shape = new CANNON.Sphere(Math.max(0.01, r));
    return this._addBody(mesh, shape, mass, kinematic);
  }

  addGround(mesh, { size = [20, 0.2, 20] } = {}) {
    const half = [size[0] / 2, size[1] / 2, size[2] / 2];
    const shape = new CANNON.Box(new CANNON.Vec3(...half));
    return this._addBody(mesh, shape, 0, false);
  }

  _addBody(mesh, shape, mass, kinematic) {
    const body = new CANNON.Body({
      mass: kinematic ? 0 : mass,
      material: this.defaultMat,
      shape,
      position: new CANNON.Vec3(mesh.position.x, mesh.position.y, mesh.position.z),
      quaternion: new CANNON.Quaternion(mesh.quaternion.x, mesh.quaternion.y, mesh.quaternion.z, mesh.quaternion.w),
      type: kinematic ? CANNON.Body.KINEMATIC : (mass === 0 ? CANNON.Body.STATIC : CANNON.Body.DYNAMIC),
      linearDamping: 0.25,
      angularDamping: 0.35,
    });
    body.allowSleep = true;
    body.sleepSpeedLimit = 0.2;
    body.sleepTimeLimit = 0.5;
    this.world.addBody(body);

    const initial = {
      position: mesh.position.clone(),
      quaternion: mesh.quaternion.clone(),
      scale: mesh.scale.clone(),
    };
    mesh.userData.physicsBody = body;
    this.bodies.set(mesh.uuid, { mesh, body, initial });
    return body;
  }

  remove(mesh) {
    const entry = this.bodies.get(mesh.uuid);
    if (!entry) return;
    this.world.removeBody(entry.body);
    this.bodies.delete(mesh.uuid);
  }

  step(dt) {
    this.world.step(1 / 60, dt, 3);
  }

  syncMeshes() {
    for (const { mesh, body } of this.bodies.values()) {
      if (body.type === CANNON.Body.STATIC) continue;
      mesh.position.set(body.position.x, body.position.y, body.position.z);
      mesh.quaternion.set(body.quaternion.x, body.quaternion.y, body.quaternion.z, body.quaternion.w);
    }
  }

  syncBodyFromMesh(mesh) {
    const entry = this.bodies.get(mesh.uuid);
    if (!entry) return;
    const { body } = entry;
    body.position.set(mesh.position.x, mesh.position.y, mesh.position.z);
    body.quaternion.set(mesh.quaternion.x, mesh.quaternion.y, mesh.quaternion.z, mesh.quaternion.w);
    body.velocity.setZero();
    body.angularVelocity.setZero();
    body.wakeUp();
  }

  applyImpulse(mesh, impulseVec3, worldPoint = null) {
    const entry = this.bodies.get(mesh.uuid);
    if (!entry) return;
    const { body } = entry;
    const impulse = new CANNON.Vec3(impulseVec3.x, impulseVec3.y, impulseVec3.z);
    if (worldPoint) {
      const point = new CANNON.Vec3(worldPoint.x, worldPoint.y, worldPoint.z);
      body.applyImpulse(impulse, point);
    } else {
      body.applyImpulse(impulse);
    }
    body.wakeUp();
  }

  reset() {
    for (const { mesh, body, initial } of this.bodies.values()) {
      mesh.position.copy(initial.position);
      mesh.quaternion.copy(initial.quaternion);
      mesh.scale.copy(initial.scale);
      body.position.set(initial.position.x, initial.position.y, initial.position.z);
      body.quaternion.set(initial.quaternion.x, initial.quaternion.y, initial.quaternion.z, initial.quaternion.w);
      body.velocity.setZero();
      body.angularVelocity.setZero();
      if (body.type === CANNON.Body.DYNAMIC) body.wakeUp();
    }
  }
}
