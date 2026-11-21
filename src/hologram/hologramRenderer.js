import * as THREE from 'three';

export class HologramRenderer {
  constructor(renderer, scene, camera) {
    this.renderer = renderer;
    this.scene = scene;
    this.baseCamera = camera;
    this.size = { w: window.innerWidth, h: window.innerHeight };
    this.target = new THREE.Vector3(0, 0.4, 0);
  }

  resize(w, h) {
    this.size.w = w;
    this.size.h = h;
  }

  render() {
    const { renderer, scene } = this;
    const w = renderer.domElement.width;
    const h = renderer.domElement.height;
    const s = Math.floor(Math.min(w, h) / 2);
    if (s <= 0) return;

    const cx = Math.floor(w / 2);
    const cy = Math.floor(h / 2);

    const basePos = this.baseCamera.position.clone();
    const dist = basePos.distanceTo(this.target);
    const baseY = basePos.y;

    renderer.setScissorTest(true);
    renderer.setClearColor(0x000000, 0);
    renderer.clear();

    const views = [
      { x: cx - s / 2, y: cy + 0,       rot: 0,              flipY: 1 },
      { x: cx,         y: cy - s / 2,   rot: Math.PI / 2,    flipY: 1 },
      { x: cx - s / 2, y: cy - s,       rot: Math.PI,        flipY: 1 },
      { x: cx - s,     y: cy - s / 2,   rot: -Math.PI / 2,   flipY: 1 },
    ];

    for (const v of views) {
      const cam = this.baseCamera.clone();
      const offset = basePos.clone().sub(this.target);
      const cos = Math.cos(v.rot);
      const sin = Math.sin(v.rot);
      const rx = offset.x * cos - offset.z * sin;
      const rz = offset.x * sin + offset.z * cos;
      cam.position.set(this.target.x + rx, baseY, this.target.z + rz);
      cam.up.set(0, 1, 0);
      cam.lookAt(this.target);
      cam.rotateZ(v.rot);
      cam.aspect = 1;
      cam.updateProjectionMatrix();

      const vx = Math.max(0, Math.floor(v.x));
      const vy = Math.max(0, Math.floor(v.y));
      renderer.setViewport(vx, vy, s, s);
      renderer.setScissor(vx, vy, s, s);
      renderer.render(scene, cam);
    }

    renderer.setScissorTest(false);
  }
}
