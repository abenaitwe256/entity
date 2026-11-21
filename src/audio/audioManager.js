import * as THREE from 'three';

export class AudioManager {
  constructor(camera) {
    this.camera = camera;
    this.ctx = null;
    this.master = null;
    this.enabled = true;
  }

  async resume() {
    if (!this.enabled) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!this.ctx) {
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0.25;
      this.master.connect(this.ctx.destination);
    }
    if (this.ctx.state === 'suspended') {
      try { await this.ctx.resume(); } catch (_) {}
    }
  }

  _beep({ freq = 440, dur = 0.08, type = 'sine', gain = 0.2, slideTo = null } = {}) {
    if (!this.ctx || this.ctx.state !== 'running') return;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t);
    if (slideTo) osc.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(g).connect(this.master);
    osc.start(t);
    osc.stop(t + dur + 0.02);
  }

  playGrab(name = 'object') {
    if (name === 'planet') this._beep({ freq: 220, slideTo: 330, dur: 0.12, type: 'triangle', gain: 0.18 });
    else if (name === 'creature') this._beep({ freq: 520, slideTo: 680, dur: 0.1, type: 'sine', gain: 0.15 });
    else this._beep({ freq: 400, slideTo: 500, dur: 0.08, type: 'sine', gain: 0.15 });
  }

  playBoop() {
    this._beep({ freq: 300, slideTo: 600, dur: 0.14, type: 'sine', gain: 0.18 });
  }

  update() {
    // Placeholder for future listener/object spatialization updates.
  }
}
