export class VoiceController {
  constructor({ onCommand, onStatus } = {}) {
    this.onCommand = onCommand || (() => {});
    this.onStatus = onStatus || (() => {});
    this.recognition = null;
    this.active = false;
    this.supported = false;
    this.restartTimer = null;
    this._init();
  }

  _init() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      this.supported = false;
      return;
    }

    this.supported = true;
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 3;

    recognition.onstart = () => this.onStatus('Listening • say grow, shrink, spin, jump or reset');
    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = (result[0]?.transcript || '').trim().toLowerCase();
        if (!transcript) continue;

        if (!result.isFinal) {
          this.onStatus('Hearing: ' + transcript);
          continue;
        }

        const command = this._parse(transcript);
        this.onStatus(command.type === 'unknown'
          ? 'Heard: "' + transcript + '" • command not recognised'
          : 'Command: ' + command.type);
        this.onCommand(command);
      }
    };

    recognition.onerror = (event) => {
      const messages = {
        'not-allowed': 'Microphone permission denied. Allow microphone access for this site.',
        'service-not-allowed': 'Speech recognition is blocked by the browser.',
        'audio-capture': 'No working microphone was found.',
        'network': 'Voice recognition needs an internet connection on this browser.',
        'no-speech': 'No speech heard • try speaking closer to the microphone.'
      };
      if (messages[event.error]) this.onStatus(messages[event.error]);
      else if (event.error !== 'aborted') console.warn('Speech recognition error:', event.error);

      if (event.error === 'not-allowed' || event.error === 'service-not-allowed' || event.error === 'audio-capture') {
        this.active = false;
      }
    };

    recognition.onend = () => {
      if (!this.active) return;
      clearTimeout(this.restartTimer);
      this.restartTimer = setTimeout(() => {
        if (!this.active) return;
        try { recognition.start(); }
        catch (error) { console.warn('Voice restart failed:', error); }
      }, 400);
    };

    this.recognition = recognition;
  }

  _parse(transcript) {
    const text = transcript.toLowerCase().replace(/[.,!?]/g, ' ').replace(/\s+/g, ' ').trim();
    const has = (...phrases) => phrases.some((phrase) => text.includes(phrase));
    let type = 'unknown';

    if (has('grow', 'bigger', 'make it big', 'larger', 'increase', 'expand')) type = 'grow';
    else if (has('shrink', 'smaller', 'make it small', 'decrease', 'reduce')) type = 'shrink';
    else if (has('spin', 'rotate', 'turn around')) type = 'spin';
    else if (has('jump', 'hop', 'bounce')) type = 'jump';
    else if (has('reset', 'restart', 'start again', 'clear scene')) type = 'reset';
    else if (has('planet', 'world', 'globe', 'select planet')) type = 'selectPlanet';
    else if (has('creature', 'animal', 'pet', 'fox', 'dog', 'cat', 'select creature')) type = 'selectCreature';
    else if (has('come here', 'come closer', 'bring it here', 'move closer', 'to me')) type = 'comeHere';

    return { type, raw: transcript };
  }

  start() {
    if (!this.supported) {
      this.onStatus('Voice recognition is not supported in this browser. Try Chrome on Android.');
      return false;
    }
    if (this.active) return true;

    clearTimeout(this.restartTimer);
    this.active = true;
    try {
      this.recognition.start();
      return true;
    } catch (error) {
      this.active = false;
      console.warn('Voice start failed:', error);
      this.onStatus('Could not start voice recognition. Tap Voice and allow microphone access.');
      return false;
    }
  }

  stop() {
    this.active = false;
    clearTimeout(this.restartTimer);
    if (this.recognition) {
      try { this.recognition.stop(); } catch (_) {}
    }
    if (this.supported) this.onStatus('Voice stopped');
  }

  toggle() {
    if (this.active) {
      this.stop();
      return false;
    }
    return this.start();
  }
}
