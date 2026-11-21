export class VoiceController {
  constructor({ onCommand, onStatus } = {}) {
    this.onCommand = onCommand || (() => {});
    this.onStatus = onStatus || (() => {});
    this.recognition = null;
    this.active = false;
    this.supported = false;
    this._init();
  }

  _init() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      this.supported = false;
      return;
    }
    this.supported = true;
    const rec = new SR();
    rec.lang = 'en-US';
    rec.continuous = true;
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        if (!res.isFinal) continue;
        const transcript = (res[0]?.transcript || '').trim().toLowerCase();
        if (!transcript) continue;
        const cmd = this._parse(transcript);
        this.onCommand(cmd);
      }
    };
    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        this.onStatus('Microphone permission denied for voice');
        this.active = false;
      } else if (e.error !== 'no-speech' && e.error !== 'aborted') {
        console.warn('Speech recognition error', e.error);
      }
    };
    rec.onend = () => {
      if (this.active) {
        try { rec.start(); } catch (_) {}
      }
    };

    this.recognition = rec;
  }

  _parse(text) {
    const raw = text;
    const has = (...words) => words.some(w => text.includes(w));
    let type = 'unknown';
    if (has('grow', 'bigger', 'larger', 'increase', 'expand')) type = 'grow';
    else if (has('shrink', 'smaller', 'decrease')) type = 'shrink';
    else if (has('spin', 'rotate', 'turn')) type = 'spin';
    else if (has('jump', 'hop', 'bounce')) type = 'jump';
    else if (has('reset', 'restart', 'clear')) type = 'reset';
    else if (has('planet', 'world', 'globe')) type = 'selectPlanet';
    else if (has('creature', 'animal', 'pet', 'fox', 'dog', 'cat')) type = 'selectCreature';
    else if (has('come here', 'come', 'here', 'closer', 'to me')) type = 'comeHere';
    return { type, raw };
  }

  start() {
    if (!this.supported) {
      this.onStatus('Voice not supported in this browser (try Chrome/Edge)');
      return false;
    }
    if (this.active) return true;
    try {
      this.recognition.start();
      this.active = true;
      this.onStatus('Listening for voice commands…');
      return true;
    } catch (e) {
      console.warn('Voice start failed', e);
      return false;
    }
  }

  stop() {
    this.active = false;
    if (this.recognition) {
      try { this.recognition.stop(); } catch (_) {}
    }
    if (this.supported) this.onStatus('Voice stopped');
  }

  toggle() {
    if (this.active) { this.stop(); return false; }
    return this.start();
  }
}
