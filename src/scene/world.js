import * as THREE from 'three';
import * as CANNON from 'cannon-es';

export class World {
  constructor(canvas, physics) {
    this.canvas = canvas;
    this.physics = physics;

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.shadowMap.enabled = true;

    this.scene = new THREE.Scene();

    this.camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.01, 100);
    this.camera.position.set(0, 1.2, 2.4);
    this.camera.lookAt(0, 0.4, 0);

    this.pickables = [];
    this.clock = new THREE.Clock();

    this._setupLights();
    this._setupEnvironment();
    this._setupObjects();
  }

  _setupLights() {
    const hemi = new THREE.HemisphereLight(0xbfdfff, 0x223344, 0.9);
    this.scene.add(hemi);

    const dir = new THREE.DirectionalLight(0xffffff, 1.1);
    dir.position.set(2, 4, 2);
    dir.castShadow = true;
    dir.shadow.mapSize.set(1024, 1024);
    dir.shadow.camera.near = 0.5;
    dir.shadow.camera.far = 20;
    this.scene.add(dir);

    const rim = new THREE.PointLight(0x7dd3fc, 0.6, 10);
    rim.position.set(-2, 1.5, -1.5);
    this.scene.add(rim);
  }

  _setupEnvironment() {
    const tableGeo = new THREE.CylinderGeometry(1.4, 1.5, 0.08, 64);
    const tableMat = new THREE.MeshStandardMaterial({ color: 0x1b2433, metalness: 0.1, roughness: 0.85 });
    const table = new THREE.Mesh(tableGeo, tableMat);
    table.position.set(0, -0.04, 0);
    table.receiveShadow = true;
    table.name = 'table';
    this.scene.add(table);
    this.physics.addGround(table, { size: [3, 0.08, 3] });

    const ringGeo = new THREE.RingGeometry(1.35, 1.42, 64);
    const ringMat = new THREE.MeshBasicMaterial({ color: 0x5eead4, transparent: true, opacity: 0.25, side: THREE.DoubleSide });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.005;
    this.scene.add(ring);
  }

  _setupObjects() {
    const planetGroup = new THREE.Group();
    planetGroup.position.set(-0.35, 0.45, 0);
    planetGroup.userData = { label: 'planet', name: 'planet', type: 'planet' };

    const planetGeo = new THREE.SphereGeometry(0.28, 48, 48);
    const planetMat = new THREE.MeshStandardMaterial({ color: 0x3b82f6, roughness: 0.7, metalness: 0.05 });
    const planet = new THREE.Mesh(planetGeo, planetMat);
    planet.castShadow = true;
    planet.receiveShadow = true;
    planetGroup.add(planet);

    const pRingGeo = new THREE.RingGeometry(0.36, 0.46, 64);
    const pRingMat = new THREE.MeshBasicMaterial({ color: 0xa5f3fc, transparent: true, opacity: 0.7, side: THREE.DoubleSide });
    const pRing = new THREE.Mesh(pRingGeo, pRingMat);
    pRing.rotation.x = Math.PI / 2.4;
    planetGroup.add(pRing);

    const blobMat = new THREE.MeshStandardMaterial({ color: 0x34d399, roughness: 0.9 });
    for (let i = 0; i < 5; i++) {
      const b = new THREE.Mesh(new THREE.SphereGeometry(0.06 + Math.random() * 0.04, 16, 16), blobMat);
      const phi = Math.random() * Math.PI * 2;
      const theta = Math.random() * Math.PI;
      const r = 0.26;
      b.position.set(
        r * Math.sin(theta) * Math.cos(phi),
        r * Math.cos(theta),
        r * Math.sin(theta) * Math.sin(phi)
      );
      planetGroup.add(b);
    }

    this.scene.add(planetGroup);
    this.physics.addSphere(planetGroup, { mass: 1.2, radius: 0.28 });
    this.pickables.push(planetGroup);
    this.planetGroup = planetGroup;
    this.planetMesh = planet;

    const creature = new THREE.Group();
    creature.position.set(0.45, 0.25, 0.15);
    creature.userData = { label: 'creature', name: 'creature', type: 'creature', baseY: 0.25 };

    const bodyMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.6 });
    const body = new THREE.Mesh(new THREE.SphereGeometry(0.16, 32, 32), bodyMat);
    body.scale.set(1.1, 0.9, 1.2);
    body.castShadow = true;
    creature.add(body);

    const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 32, 32), bodyMat);
    head.position.set(0, 0.12, 0.16);
    head.castShadow = true;
    creature.add(head);

    const eyeMat = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.2 });
    const eyeGeo = new THREE.SphereGeometry(0.018, 16, 16);
    const eyeL = new THREE.Mesh(eyeGeo, eyeMat);
    eyeL.position.set(-0.035, 0.14, 0.255);
    const eyeR = eyeL.clone();
    eyeR.position.x = 0.035;
    creature.add(eyeL, eyeR);

    const earGeo = new THREE.ConeGeometry(0.03, 0.07, 16);
    const earMat = new THREE.MeshStandardMaterial({ color: 0xfbbf24 });
    const earL = new THREE.Mesh(earGeo, earMat);
    earL.position.set(-0.06, 0.22, 0.12);
    earL.rotation.z = 0.3;
    const earR = earL.clone();
    earR.position.x = 0.06;
    earR.rotation.z = -0.3;
    creature.add(earL, earR);

    this.scene.add(creature);
    this.physics.addSphere(creature, { mass: 0.8, radius: 0.18 });
    this.pickables.push(creature);
    this.creature = creature;

    const crystal = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.09, 0),
      new THREE.MeshStandardMaterial({ color: 0xa78bfa, metalness: 0.3, roughness: 0.25, emissive: 0x312e81, emissiveIntensity: 0.25 })
    );
    crystal.position.set(0.05, 0.5, -0.45);
    crystal.castShadow = true;
    crystal.userData = { label: 'crystal', name: 'crystal', type: 'prop' };
    this.scene.add(crystal);
    this.physics.addSphere(crystal, { mass: 0.4, radius: 0.09 });
    this.pickables.push(crystal);
    this.crystal = crystal;
  }

  getDefaultTarget() {
    return this.planetGroup || this.pickables[0];
  }

  scaleObject(obj, factor) {
    if (!obj) return;
    const s = obj.scale.x * factor;
    const clamped = THREE.MathUtils.clamp(s, 0.4, 2.5);
    obj.scale.setScalar(clamped);
    const body = obj.userData.physicsBody;
    if (body) {
      body.wakeUp();
    }
  }

  spinObject(obj) {
    if (!obj) return;
    const body = obj.userData.physicsBody;
    if (body) {
      body.angularVelocity.set(
        (Math.random() - 0.5) * 2,
        4 + Math.random() * 4,
        (Math.random() - 0.5) * 2
      );
      body.wakeUp();
    } else {
      obj.userData.spin = (obj.userData.spin || 0) + 6;
    }
  }

  jumpObject(obj) {
    if (!obj) return;
    const body = obj.userData.physicsBody;
    if (body) {
      body.applyImpulse(new CANNON.Vec3(0, body.mass * 2.2, 0), body.position);
      body.wakeUp();
    } else {
      obj.position.y += 0.2;
    }
  }

  pullTowardCamera(obj, camera) {
    if (!obj) return;
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    const targetPos = camera.position.clone().add(dir.multiplyScalar(0.8));
    targetPos.y = Math.max(0.2, targetPos.y);
    const body = obj.userData.physicsBody;
    if (body) {
      const impulse = new CANNON.Vec3(
        (targetPos.x - body.position.x) * body.mass * 1.5,
        (targetPos.y - body.position.y) * body.mass * 1.5 + body.mass * 0.5,
        (targetPos.z - body.position.z) * body.mass * 1.5
      );
      body.applyImpulse(impulse, body.position);
      body.wakeUp();
    } else {
      obj.position.lerp(targetPos, 0.5);
    }
  }

  update(dt) {
    const t = this.clock.getElapsedTime();
    if (this.creature) {
      const body = this.creature.userData.physicsBody;
      if (body) {
        const speed = body.velocity.length();
        if (speed < 0.05) {
          this.creature.rotation.y += dt * 0.3;
        }
      }
    }
    if (this.planetMesh) {
      this.planetMesh.rotation.y += dt * 0.15;
    }
    if (this.crystal) {
      const b = this.crystal.userData.physicsBody;
      if (b && b.velocity.length() < 0.02) {
        b.position.y += Math.sin(t * 2) * 0.0008;
      }
      this.crystal.rotation.y += dt * 0.8;
      this.crystal.rotation.x += dt * 0.3;
    }
  }

  render() {
    this.renderer.setScissorTest(false);
    this.renderer.setViewport(0, 0, this.canvas.width, this.canvas.height);
    this.renderer.render(this.scene, this.camera);
  }

  resize(w, h) {
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h, false);
  }

  reset() {
    if (this.planetMesh) this.planetMesh.rotation.set(0, 0, 0);
    if (this.creature) this.creature.rotation.set(0, 0, 0);
    if (this.crystal) this.crystal.rotation.set(0, 0, 0);
  }
}
