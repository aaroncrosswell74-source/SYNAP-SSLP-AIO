#!/usr/bin/env python3
"""
prosody.py - Emotional Speech Prosody Engine
Applies emotion-based modulation to TTS audio.

Zero VRAM. Pure CPU. Numpy/Scipy.
"""

import numpy as np
import scipy.signal as signal
import scipy.ndimage as ndimage
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# EMOTION PRESETS
# ============================================================================

@dataclass
class ProsodyPreset:
    """Emotion-based prosody parameters"""
    speed: float = 1.0           # 0.5 - 2.0
    pitch_shift: float = 0.0     # Semitones (-6 to +6)
    breath_intensity: float = 0.0  # 0.0 - 1.0
    amplitude_scale: float = 1.0  # 0.5 - 1.5
    attack_ms: float = 10.0      # Attack time in ms
    decay_ms: float = 50.0       # Decay time in ms
    tremolo_depth: float = 0.0   # 0.0 - 0.5
    tremolo_rate: float = 5.0    # Hz
    vibrato_depth: float = 0.0   # 0.0 - 0.3
    vibrato_rate: float = 6.0    # Hz

# Emotion Presets
EMOTION_PRESETS: Dict[str, ProsodyPreset] = {
    "neutral": ProsodyPreset(
        speed=1.0,
        pitch_shift=0.0,
        breath_intensity=0.0,
        amplitude_scale=1.0,
        attack_ms=10.0,
        decay_ms=50.0,
        tremolo_depth=0.0,
        vibrato_depth=0.0
    ),
    
    "anger": ProsodyPreset(
        speed=1.4,
        pitch_shift=-1.0,
        breath_intensity=0.3,
        amplitude_scale=1.4,
        attack_ms=5.0,
        decay_ms=30.0,
        tremolo_depth=0.1,
        vibrato_depth=0.0
    ),
    
    "sadness": ProsodyPreset(
        speed=0.75,
        pitch_shift=-3.0,
        breath_intensity=0.5,
        amplitude_scale=0.75,
        attack_ms=20.0,
        decay_ms=80.0,
        tremolo_depth=0.0,
        vibrato_depth=0.05
    ),
    
    "dismissal": ProsodyPreset(
        speed=0.9,
        pitch_shift=-2.0,
        breath_intensity=0.1,
        amplitude_scale=0.85,
        attack_ms=8.0,
        decay_ms=40.0,
        tremolo_depth=0.0,
        vibrato_depth=0.0
    ),
    
    "mourning": ProsodyPreset(
        speed=0.5,
        pitch_shift=-4.0,
        breath_intensity=0.7,
        amplitude_scale=0.6,
        attack_ms=30.0,
        decay_ms=120.0,
        tremolo_depth=0.15,
        vibrato_depth=0.1
    ),
    
    "joy": ProsodyPreset(
        speed=1.2,
        pitch_shift=1.0,
        breath_intensity=0.2,
        amplitude_scale=1.2,
        attack_ms=8.0,
        decay_ms=40.0,
        tremolo_depth=0.05,
        vibrato_depth=0.0
    ),
    
    "excitement": ProsodyPreset(
        speed=1.6,
        pitch_shift=2.0,
        breath_intensity=0.4,
        amplitude_scale=1.3,
        attack_ms=5.0,
        decay_ms=25.0,
        tremolo_depth=0.08,
        vibrato_depth=0.0
    ),
    
    "fear": ProsodyPreset(
        speed=0.85,
        pitch_shift=-2.0,
        breath_intensity=0.6,
        amplitude_scale=0.7,
        attack_ms=15.0,
        decay_ms=60.0,
        tremolo_depth=0.2,
        vibrato_depth=0.05
    ),
    
    "love": ProsodyPreset(
        speed=0.9,
        pitch_shift=0.5,
        breath_intensity=0.3,
        amplitude_scale=0.9,
        attack_ms=15.0,
        decay_ms=60.0,
        tremolo_depth=0.0,
        vibrato_depth=0.03
    )
}

# ============================================================================
# PROSODY ENGINE
# ============================================================================

class ProsodyEngine:
    """
    Apply emotional prosody to PCM audio.
    Zero VRAM. Pure CPU.
    """
    
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.last_emotion = "neutral"
        logger.info(f"ProsodyEngine initialized: {sample_rate}Hz")
    
    def apply_prosody(
        self,
        pcm_bytes: bytes,
        emotion: str = "neutral",
        custom_params: Optional[Dict[str, float]] = None
    ) -> bytes:
        """
        Apply emotional prosody to PCM audio.
        
        Args:
            pcm_bytes: Raw PCM audio (int16)
            emotion: Emotion preset name
            custom_params: Override specific parameters
        
        Returns:
            Processed PCM bytes (int16)
        """
        if not pcm_bytes:
            return pcm_bytes
        
        # Get preset
        preset = EMOTION_PRESETS.get(emotion.lower(), EMOTION_PRESETS["neutral"])
        
        # Override with custom params
        if custom_params:
            for key, value in custom_params.items():
                if hasattr(preset, key):
                    setattr(preset, key, value)
        
        # Convert to float for processing
        pcm_float = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Apply effects
        processed = self._apply_pitch_shift(pcm_float, preset.pitch_shift)
        processed = self._apply_speed_change(processed, preset.speed)
        processed = self._apply_amplitude_envelope(processed, preset.attack_ms, preset.decay_ms)
        processed = processed * preset.amplitude_scale
        
        if preset.tremolo_depth > 0:
            processed = self._apply_tremolo(processed, preset.tremolo_depth, preset.tremolo_rate)
        
        if preset.vibrato_depth > 0:
            processed = self._apply_vibrato(processed, preset.vibrato_depth, preset.vibrato_rate)
        
        if preset.breath_intensity > 0:
            processed = self._inject_breath(processed, preset.breath_intensity)
        
        # Clip and convert back to int16
        processed = np.clip(processed, -1.0, 1.0)
        processed_int16 = (processed * 32767.0).astype(np.int16)
        
        self.last_emotion = emotion
        return processed_int16.tobytes()
    
    # ========================================================================
    # AUDIO EFFECTS
    # ========================================================================
    
    def _apply_pitch_shift(self, audio: np.ndarray, semitones: float) -> np.ndarray:
        """Shift pitch by semitones using resampling + resample"""
        if abs(semitones) < 0.1:
            return audio
        
        # Resample to shift pitch
        ratio = 2.0 ** (semitones / 12.0)
        new_len = int(len(audio) / ratio)
        
        # Resample using scipy
        import scipy.signal as signal
        shifted = signal.resample(audio, new_len)
        
        # Resample back to original length
        if len(shifted) != len(audio):
            shifted = signal.resample(shifted, len(audio))
        
        return shifted
    
    def _apply_speed_change(self, audio: np.ndarray, speed: float) -> np.ndarray:
        """Change playback speed without changing pitch"""
        if abs(speed - 1.0) < 0.01:
            return audio
        
        # Simple resampling
        new_len = int(len(audio) / speed)
        import scipy.signal as signal
        return signal.resample(audio, new_len)
    
    def _apply_amplitude_envelope(
        self,
        audio: np.ndarray,
        attack_ms: float,
        decay_ms: float
    ) -> np.ndarray:
        """Apply attack/decay envelope to audio"""
        if attack_ms <= 0 and decay_ms <= 0:
            return audio
        
        attack_samples = int(attack_ms * self.sample_rate / 1000)
        decay_samples = int(decay_ms * self.sample_rate / 1000)
        
        envelope = np.ones(len(audio))
        
        # Attack: ramp up
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0.01, 1.0, attack_samples)
        
        # Decay: ramp down
        if decay_samples > 0 and decay_samples < len(audio):
            start = len(audio) - decay_samples
            envelope[start:] = np.linspace(1.0, 0.01, decay_samples)
        
        return audio * envelope
    
    def _apply_tremolo(
        self,
        audio: np.ndarray,
        depth: float,
        rate: float
    ) -> np.ndarray:
        """Apply tremolo (amplitude modulation)"""
        t = np.arange(len(audio)) / self.sample_rate
        tremolo = 1.0 - depth * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t))
        return audio * tremolo
    
    def _apply_vibrato(
        self,
        audio: np.ndarray,
        depth: float,
        rate: float
    ) -> np.ndarray:
        """Apply vibrato (pitch modulation)"""
        # Simple vibrato using delay modulation
        delay_samples = int(depth * 0.003 * self.sample_rate)
        if delay_samples < 1:
            return audio
        
        t = np.arange(len(audio)) / self.sample_rate
        delay = delay_samples * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t))
        
        # Apply delay using interpolation
        import scipy.signal as signal
        output = np.zeros_like(audio)
        
        for i in range(len(audio)):
            idx = int(i - delay[i])
            if 0 <= idx < len(audio):
                output[i] = audio[idx]
        
        return output
    
    def _inject_breath(self, audio: np.ndarray, intensity: float) -> np.ndarray:
        """Inject soft breath sounds"""
        # Generate breath noise
        breath = np.random.randn(len(audio)) * intensity * 0.1
        
        # Apply envelope (soft start/end)
        breath_samples = int(0.1 * self.sample_rate)  # 100ms breath
        if breath_samples > 0:
            envelope = np.ones(len(breath))
            if breath_samples < len(breath):
                envelope[:breath_samples] = np.linspace(0.01, 1.0, breath_samples)
                envelope[-breath_samples:] = np.linspace(1.0, 0.01, breath_samples)
            breath = breath * envelope
        
        return audio + breath
    
    def apply_emotion_from_state(
        self,
        pcm_bytes: bytes,
        emotional_state: Dict[str, float]
    ) -> bytes:
        """
        Automatically select emotion based on emotional state.
        
        Args:
            pcm_bytes: Raw PCM audio
            emotional_state: Dict with valence/arousal
        
        Returns:
            Processed PCM bytes
        """
        valence = emotional_state.get("valence", 0.5)
        arousal = emotional_state.get("arousal", 0.5)
        mood = emotional_state.get("mood", "neutral")
        
        # Map valence/arousal to emotion
        if arousal > 0.8:
            emotion = "excitement" if valence > 0.5 else "anger"
        elif valence > 0.7:
            emotion = "joy" if arousal > 0.5 else "love"
        elif valence < 0.3:
            emotion = "sadness" if arousal < 0.5 else "mourning"
        elif arousal < 0.3:
            emotion = "neutral"
        else:
            emotion = mood if mood in EMOTION_PRESETS else "neutral"
        
        return self.apply_prosody(pcm_bytes, emotion)
    
    def get_preset(self, emotion: str) -> Dict[str, float]:
        """Get emotion preset parameters"""
        preset = EMOTION_PRESETS.get(emotion.lower(), EMOTION_PRESETS["neutral"])
        return {
            "speed": preset.speed,
            "pitch_shift": preset.pitch_shift,
            "breath_intensity": preset.breath_intensity,
            "amplitude_scale": preset.amplitude_scale,
            "attack_ms": preset.attack_ms,
            "decay_ms": preset.decay_ms,
            "tremolo_depth": preset.tremolo_depth,
            "vibrato_depth": preset.vibrato_depth
        }
    
    def get_emotions(self) -> list:
        """Get list of available emotions"""
        return list(EMOTION_PRESETS.keys())


# ============================================================================
# STANDALONE TEST
# ============================================================================

def test_prosody():
    """Test prosody with synthetic audio"""
    import time
    
    # Generate test tone
    sample_rate = 24000
    duration = 2.0
    t = np.linspace(0, duration, int(duration * sample_rate))
    test_tone = np.sin(2 * np.pi * 440 * t) * 0.5
    
    # Convert to PCM
    pcm = (test_tone * 32767.0).astype(np.int16).tobytes()
    
    # Apply prosody
    engine = ProsodyEngine(sample_rate)
    
    print("Emotions:", engine.get_emotions())
    
    for emotion in ["neutral", "anger", "sadness", "joy", "excitement", "fear"]:
        print(f"\n🎭 Applying {emotion}...")
        processed = engine.apply_prosody(pcm, emotion)
        print(f"   Input: {len(pcm)} bytes → Output: {len(processed)} bytes")
        print(f"   Preset: {engine.get_preset(emotion)}")


if __name__ == "__main__":
    test_prosody()
    print("\n✅ Prosody engine ready!")
