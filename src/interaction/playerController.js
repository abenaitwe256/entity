import * as THREE from 'three';

export class PlayerController {
  constructor(world) {
    this.world = world;
    this.keys = new Set();
    this.move = new THREE.Vector2();
    this.speed = 4.2;
    this.yaw = 0;
    this.player = this._createPlayer();
    world.scene.add(this.player);
    this._createTouchControls();
    this._onKeyDown = e => { const k=e.key.toLowerCase(); if(['w','a','s','d','arrowup','arrowdown','arrowleft','arrowright','shift'].includes(k)){this.keys.add(k); if(k.startsWith('arrow'))e.preventDefault();} };
    this._onKeyUp = e => this.keys.delete(e.key.toLowerCase());
    window.addEventListener('keydown',this._onKeyDown);
    window.addEventListener('keyup',this._onKeyUp);
  }

  _createPlayer() {
    const g=new THREE.Group(); g.position.set(0,0,3.7);
    const skin=new THREE.MeshStandardMaterial({color:0x9a684b,roughness:0.8});
    const jacket=new THREE.MeshStandardMaterial({color:0x253b50,roughness:0.7});
    const pants=new THREE.MeshStandardMaterial({color:0x242a35,roughness:0.9});
    const torso=new THREE.Mesh(new THREE.CapsuleGeometry(0.25,0.48,5,10),jacket);torso.position.y=0.92;torso.castShadow=true;g.add(torso);
    const head=new THREE.Mesh(new THREE.SphereGeometry(0.17,20,16),skin);head.position.y=1.48;head.castShadow=true;g.add(head);
    const legGeo=new THREE.CapsuleGeometry(0.09,0.42,4,8);
    for(const x of [-0.13,0.13]){const leg=new THREE.Mesh(legGeo,pants);leg.position.set(x,0.34,0);leg.castShadow=true;g.add(leg);}
    const armGeo=new THREE.CapsuleGeometry(0.075,0.38,4,8);
    for(const x of [-0.32,0.32]){const arm=new THREE.Mesh(armGeo,jacket);arm.position.set(x,0.94,0);arm.rotation.z=x<0?-0.12:0.12;arm.castShadow=true;g.add(arm);}
    const shadow=new THREE.Mesh(new THREE.CircleGeometry(0.38,24),new THREE.MeshBasicMaterial({color:0x111820,transparent:true,opacity:0.28}));
    shadow.rotation.x=-Math.PI/2;shadow.position.y=0.015;g.add(shadow);
    return g;
  }

  _createTouchControls() {
    const root=document.createElement('div');root.id='mobile-controls';
    root.innerHTML='<div id="move-stick"><div id="stick-knob"></div></div><button id="run-button" type="button">RUN</button>';
    document.body.appendChild(root);
    const pad=root.querySelector('#move-stick'),knob=root.querySelector('#stick-knob');
    let activeId=null,center=null;
    const move=e=>{if(e.pointerId!==activeId)return;const dx=e.clientX-center.x,dy=e.clientY-center.y;const len=Math.max(1,Math.hypot(dx,dy));const scale=Math.min(1,48/len);const x=dx*scale,y=dy*scale;knob.style.transform=`translate(${x}px,${y}px)`;this.move.set(x/48,-y/48);};
    const end=e=>{if(e.pointerId!==activeId)return;activeId=null;this.move.set(0,0);knob.style.transform='translate(0px,0px)';};
    pad.addEventListener('pointerdown',e=>{e.preventDefault();activeId=e.pointerId;const r=pad.getBoundingClientRect();center={x:r.left+r.width/2,y:r.top+r.height/2};pad.setPointerCapture(e.pointerId);move(e);});
    pad.addEventListener('pointermove',move);pad.addEventListener('pointerup',end);pad.addEventListener('pointercancel',end);
    const run=root.querySelector('#run-button');
    run.addEventListener('pointerdown',e=>{e.preventDefault();this.keys.add('shift');});
    ['pointerup','pointercancel','pointerleave'].forEach(type=>run.addEventListener(type,()=>this.keys.delete('shift')));
  }

  update(dt) {
    const x=(this.keys.has('d')||this.keys.has('arrowright')?1:0)-(this.keys.has('a')||this.keys.has('arrowleft')?1:0)+this.move.x;
    const z=(this.keys.has('w')||this.keys.has('arrowup')?1:0)-(this.keys.has('s')||this.keys.has('arrowdown')?1:0)+this.move.y;
    const input=new THREE.Vector2(x,z); if(input.lengthSq()>1)input.normalize();
    if(input.lengthSq()>0.001){
      const run=this.keys.has('shift')?1.65:1;
      this.player.position.x+=input.x*this.speed*run*dt;
      this.player.position.z+=input.y*this.speed*run*dt;
      this.player.position.x=THREE.MathUtils.clamp(this.player.position.x,-22,22);
      this.player.position.z=THREE.MathUtils.clamp(this.player.position.z,-22,22);
      this.player.rotation.y=Math.atan2(input.x,input.y);
    }
    const target=this.player.position.clone().add(new THREE.Vector3(0,1.05,0));
    const cameraTarget=this.player.position.clone().add(new THREE.Vector3(0,4.2,7.2));
    this.world.camera.position.lerp(cameraTarget,Math.min(1,dt*4.5));
    this.world.camera.lookAt(target);
  }

  dispose(){window.removeEventListener('keydown',this._onKeyDown);window.removeEventListener('keyup',this._onKeyUp);}
}
