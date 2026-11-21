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
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.12;

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
    this.scene.add(new THREE.HemisphereLight(0xc5dcff, 0x34452f, 1.15));
    const sun = new THREE.DirectionalLight(0xffedcf, 2.4);
    sun.position.set(-12,22,10); sun.castShadow=true;
    sun.shadow.mapSize.set(2048,2048);
    Object.assign(sun.shadow.camera,{left:-24,right:24,top:24,bottom:-24,near:0.5,far:75});
    sun.shadow.bias=-0.00015; this.scene.add(sun);
    this.scene.add(new THREE.AmbientLight(0xffffff,0.28));
  }

  _setupEnvironment() {
    // Fictional procedural downtown district: original geometry, not copied game assets.
    this.scene.background = new THREE.Color(0x91b8d0);
    this.scene.fog = new THREE.Fog(0x91b8d0, 24, 78);
    const mat=(color,roughness=0.9,metalness=0)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
    const ground=new THREE.Mesh(new THREE.PlaneGeometry(100,100),mat(0x55764c));
    ground.rotation.x=-Math.PI/2; ground.position.y=-0.09; ground.receiveShadow=true; this.scene.add(ground);
    this.physics.addGround(ground,{size:[100,0.18,100]});
    const asphalt=mat(0x252b31), concrete=mat(0x999990), yellow=mat(0xf2d16b);
    const road=new THREE.Mesh(new THREE.PlaneGeometry(44,8),asphalt);
    road.rotation.x=-Math.PI/2; road.position.y=-0.075; road.receiveShadow=true; this.scene.add(road);
    const cross=new THREE.Mesh(new THREE.PlaneGeometry(8,44),asphalt);
    cross.rotation.x=-Math.PI/2; cross.position.y=-0.073; cross.receiveShadow=true; this.scene.add(cross);
    for(let i=-19;i<=19;i+=3){
      const d=new THREE.Mesh(new THREE.BoxGeometry(1.35,0.012,0.09),yellow); d.position.set(i,-0.06,0); this.scene.add(d);
      const e=new THREE.Mesh(new THREE.BoxGeometry(0.09,0.012,1.35),yellow); e.position.set(0,-0.059,i); this.scene.add(e);
    }
    for(const z of [-5.1,5.1]){const p=new THREE.Mesh(new THREE.BoxGeometry(44,0.18,2.1),concrete);p.position.set(0,0.015,z);p.receiveShadow=true;this.scene.add(p);}
    for(const x of [-5.1,5.1]){const p=new THREE.Mesh(new THREE.BoxGeometry(2.1,0.18,44),concrete);p.position.set(x,0.015,0);p.receiveShadow=true;this.scene.add(p);}
    const facade=[0x697b88,0x9b8875,0x536b78,0xb0a18d,0x65705f,0x7a7180].map(c=>mat(c));
    const glass=mat(0x263e50,0.22,0.55), windows=mat(0x9dc5d3,0.25,0.25);
    const rand=n=>{const v=Math.sin(n*127.1)*43758.5453;return v-Math.floor(v);};
    let id=0;
    for(let x=-18;x<=18;x+=6)for(let z=-18;z<=18;z+=6){
      if(Math.abs(x)<7||Math.abs(z)<7)continue;
      const k=id++,w=3.1+rand(k+2)*1.7,d=3.1+rand(k+8)*1.7,h=3.8+rand(k+15)*10.5;
      const b=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),facade[k%facade.length]);
      b.position.set(x+(rand(k+3)-0.5)*0.8,h/2,z+(rand(k+4)-0.5)*0.8);b.castShadow=true;b.receiveShadow=true;this.scene.add(b);
      const roof=new THREE.Mesh(new THREE.BoxGeometry(w+0.12,0.16,d+0.12),glass);roof.position.set(b.position.x,h+0.07,b.position.z);roof.castShadow=true;this.scene.add(roof);
      for(let f=1;f<Math.floor(h/1.65);f++)for(let c=-1;c<=1;c++){
        const pane=new THREE.Mesh(new THREE.BoxGeometry(0.48,0.55,0.035),windows);
        pane.position.set(b.position.x+c*0.82,f*1.55,b.position.z+d/2+0.022);this.scene.add(pane);
      }
    }
    const foliage=mat(0x2f6742),wood=mat(0x64462e);
    for(let i=0;i<26;i++){
      const x=-19+(i%13)*3.15,z=i<13?-7.2:7.2;if(Math.abs(x)<7)continue;
      const trunk=new THREE.Mesh(new THREE.CylinderGeometry(0.12,0.17,1.15,8),wood);trunk.position.set(x,0.55,z);trunk.castShadow=true;this.scene.add(trunk);
      const crown=new THREE.Mesh(new THREE.IcosahedronGeometry(0.72,1),foliage);crown.position.set(x,1.55,z);crown.castShadow=true;this.scene.add(crown);
    }
    const poleMat=mat(0x343b43,0.35,0.7),lampMat=new THREE.MeshStandardMaterial({color:0xffe4a1,emissive:0xffb84d,emissiveIntensity:0.35});
    for(const x of [-8,8])for(const z of [-8,8]){
      const pole=new THREE.Mesh(new THREE.CylinderGeometry(0.055,0.075,3.5,10),poleMat);pole.position.set(x,1.75,z);pole.castShadow=true;this.scene.add(pole);
      const arm=new THREE.Mesh(new THREE.BoxGeometry(0.75,0.06,0.06),poleMat);arm.position.set(x+0.32,3.42,z);this.scene.add(arm);
      const lamp=new THREE.Mesh(new THREE.SphereGeometry(0.13,12,12),lampMat);lamp.position.set(x+0.65,3.38,z);this.scene.add(lamp);
    }
    const colors=[0xb83f35,0x263c58,0xd5d0c5];
    for(let i=0;i<3;i++){
      const car=new THREE.Group(),paint=mat(colors[i],0.28,0.65);
      const body=new THREE.Mesh(new THREE.BoxGeometry(1.65,0.42,0.78),paint);body.position.y=0.42;body.castShadow=true;car.add(body);
      const cabin=new THREE.Mesh(new THREE.BoxGeometry(0.88,0.42,0.68),glass);cabin.position.set(-0.08,0.81,0);cabin.castShadow=true;car.add(cabin);
      const tire=mat(0x17191c);
      for(const wx of [-0.52,0.52])for(const wz of [-0.4,0.4]){const wheel=new THREE.Mesh(new THREE.CylinderGeometry(0.19,0.19,0.12,16),tire);wheel.rotation.x=Math.PI/2;wheel.position.set(wx,0.22,wz);car.add(wheel);}
      car.position.set(-2.1+i*2.1,0,-6.2);car.rotation.y=Math.PI/2;this.scene.add(car);
    }
    const plaza=new THREE.Mesh(new THREE.CylinderGeometry(1.7,1.75,0.12,48),mat(0x34414a,0.78,0.15));
    plaza.position.set(0,0.04,0);plaza.receiveShadow=true;this.scene.add(plaza);
    const ring=new THREE.Mesh(new THREE.RingGeometry(1.62,1.69,64),new THREE.MeshBasicMaterial({color:0x5eead4,transparent:true,opacity:0.48,side:THREE.DoubleSide}));
    ring.rotation.x=-Math.PI/2;ring.position.y=0.105;this.scene.add(ring);
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
