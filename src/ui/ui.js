export function initUI({ onModeChange, onCameraToggle, onVoiceToggle, onReset }) {
  const btnScreen = document.getElementById('btn-screen');
  const btnHologram = document.getElementById('btn-hologram');
  const btnCamera = document.getElementById('btn-camera');
  const btnVoice = document.getElementById('btn-voice');
  const btnReset = document.getElementById('btn-reset');

  let mode = 'screen';
  let cameraOn = false;
  let voiceOn = false;

  function setMode(next) {
    mode = next;
    btnScreen.classList.toggle('active', mode === 'screen');
    btnHologram.classList.toggle('active', mode === 'hologram');
    onModeChange?.(mode);
  }

  btnScreen.addEventListener('click', () => setMode('screen'));
  btnHologram.addEventListener('click', () => setMode('hologram'));

  btnCamera.addEventListener('click', () => {
    cameraOn = !cameraOn;
    btnCamera.classList.toggle('active', cameraOn);
    onCameraToggle?.(cameraOn);
  });

  function setVoice(on) {
    voiceOn = on;
    btnVoice.classList.toggle('listening', voiceOn);
    btnVoice.classList.toggle('active', voiceOn);
  }

  btnVoice.addEventListener('click', () => {
    setVoice(!voiceOn);
    onVoiceToggle?.(voiceOn);
  });

  btnReset.addEventListener('click', () => onReset?.());

  return {
    setCameraActive(on) {
      cameraOn = on;
      btnCamera.classList.toggle('active', cameraOn);
    },
    setVoiceActive(on) {
      setVoice(on);
    },
    toggleVoice() {
      setVoice(!voiceOn);
      onVoiceToggle?.(voiceOn);
    },
  };
}
