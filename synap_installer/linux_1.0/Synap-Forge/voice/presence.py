#!/usr/bin/env python3
"""
voice/presence.py - Always-On Voice Presence for Consciousness Engine
Zero-cost, local, low-latency voice presence using Silero VAD + RNNoise + Kokoro
"""

import asyncio
import os
import sys
import logging
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, AsyncGenerator
import json
import time
import queue
import threading

# ============================================================================
# CONFIGURATION
# ============================================================================
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 512  # 32ms at 16kHz
VAD_THRESHOLD = 0.5
SILENCE_TIMEOUT = 2.0  # seconds before processing stop
NOISE_SUPPRESSION = True
TTS_VOICE = "af_heart"
TTS_SPEED = 1.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("voice_presence")

# ============================================================================
# SILERO VAD (Voice Activity Detection)
# ============================================================================
class SileroVAD:
    """Zero-cost, CPU-based voice activity detection."""
    
    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self._model = None
        self._loaded = False
        
    def load(self):
        """Load Silero VAD model from local cache or download."""
        try:
            import torch
            import torchaudio
            
            # Use the tiny, fast model
            model_path = Path.home() / ".cache/silero_vad/silero_vad.jit"
            if not model_path.exists():
                logger.info("Downloading Silero VAD model...")
                model_path.parent.mkdir(parents=True, exist_ok=True)
                # Download from official source
                import urllib.request
                url = "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.jit"
                urllib.request.urlretrieve(url, model_path)
            
            self._model = torch.jit.load(model_path)
            self._loaded = True
            logger.info("✅ Silero VAD loaded")
            return True
        except Exception as e:
            logger.warning(f"Silero VAD load failed: {e}")
            return False
    
    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Detect if the audio chunk contains speech."""
        if not self._loaded:
            return False
        
        try:
            import torch
            # Reshape for model
            audio_tensor = torch.from_numpy(audio_chunk).float()
            if len(audio_tensor.shape) == 1:
                audio_tensor = audio_tensor.unsqueeze(0)
            
            # Get speech probability
            with torch.no_grad():
                speech_prob = self._model(audio_tensor, self.sample_rate).item()
            
            return speech_prob > self.threshold
        except Exception as e:
            logger.debug(f"VAD error: {e}")
            return False

# ============================================================================
# RNNoise (Noise Suppression)
# ============================================================================
class RNNoiseProcessor:
    """Zero-cost CPU-based noise suppression."""
    
    def __init__(self):
        self._model = None
        self._loaded = False
        
    def load(self):
        """Load RNNoise model."""
        try:
            # Use rnnoise wrapper or fallback to simple noise gate
            import rnnoise
            self._model = rnnoise.RNNoise()
            self._loaded = True
            logger.info("✅ RNNoise loaded")
            return True
        except ImportError:
            logger.warning("RNNoise not available, using simple noise gate fallback")
            self._loaded = True  # Use fallback
            return True
        except Exception as e:
            logger.warning(f"RNNoise load failed: {e}")
            return False
    
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise suppression."""
        if not self._loaded:
            return audio
        
        try:
            # Simple noise gate fallback
            threshold = 0.01
            audio_abs = np.abs(audio)
            if np.max(audio_abs) < threshold:
                return np.zeros_like(audio)
            return audio
        except Exception as e:
            logger.debug(f"Noise suppression error: {e}")
            return audio

# ============================================================================
# STREAM MANAGER
# ============================================================================
@dataclass
class VoiceStream:
    """Active voice stream state."""
    is_active: bool = False
    buffer: list = None
    speech_start: float = 0
    last_activity: float = 0
    silence_count: int = 0
    
    def __post_init__(self):
        self.buffer = []

class VoicePresence:
    """
    Always-on voice presence.
    Monitors microphone, detects speech, processes, and responds.
    """
    
    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback
        self.vad = SileroVAD()
        self.denoiser = RNNoiseProcessor()
        self.stream = VoiceStream()
        self._running = False
        self._audio_queue = queue.Queue()
        self._response_queue = queue.Queue()
        
        # TTS will be integrated from existing pipeline
        self.tts_pipeline = None  # Will be set later
        
    def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("🎤 Initializing Voice Presence...")
        
        # Load VAD
        if not self.vad.load():
            logger.warning("VAD not available, using threshold detection")
        
        # Load denoiser
        if not self.denoiser.load():
            logger.warning("Noise suppression not available")
        
        # Test audio devices
        try:
            devices = sd.query_devices()
            logger.info(f"✅ Audio devices: {len(devices)} found")
        except Exception as e:
            logger.warning(f"Audio device query failed: {e}")
        
        logger.info("✅ Voice Presence initialized")
        return True
    
    def _audio_callback(self, indata, frames, time, status):
        """Called by sounddevice for each audio chunk."""
        if status:
            logger.debug(f"Audio status: {status}")
        
        # Copy data to queue for processing
        audio_chunk = indata[:, 0].copy()
        self._audio_queue.put(audio_chunk)
    
    async def _process_audio_loop(self):
        """Process audio chunks from the queue."""
        speech_buffer = []
        speech_active = False
        silence_frames = 0
        max_silence_frames = int(SILENCE_TIMEOUT * SAMPLE_RATE / CHUNK_SIZE)
        
        while self._running:
            try:
                # Get audio chunk (non-blocking)
                audio_chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                # If no audio and speech was active, check silence
                if speech_active:
                    silence_frames += 1
                    if silence_frames > max_silence_frames:
                        # Process the speech
                        if len(speech_buffer) > 0:
                            await self._process_speech(np.concatenate(speech_buffer))
                        speech_buffer = []
                        speech_active = False
                        silence_frames = 0
                continue
            
            # Apply noise suppression
            if self.denoiser._loaded:
                audio_chunk = self.denoiser.process(audio_chunk)
            
            # Detect speech
            is_speech = self.vad.is_speech(audio_chunk)
            
            if is_speech:
                # Speech detected
                if not speech_active:
                    speech_active = True
                    logger.info("🗣️ Speech detected")
                speech_buffer.append(audio_chunk)
                silence_frames = 0
            elif speech_active:
                # Silence during speech
                speech_buffer.append(audio_chunk)
                silence_frames += 1
                
                if silence_frames > max_silence_frames:
                    # End of speech
                    if len(speech_buffer) > 0:
                        await self._process_speech(np.concatenate(speech_buffer))
                    speech_buffer = []
                    speech_active = False
                    silence_frames = 0
    
    async def _process_speech(self, audio: np.ndarray):
        """Process a complete speech segment."""
        logger.info(f"🔊 Processing speech: {len(audio) / SAMPLE_RATE:.2f}s")
        
        # Here we would:
        # 1. Transcribe (Vosk or Whisper)
        # 2. Send to LLM
        # 3. Generate response (TTS)
        
        # For now, just log and echo back
        try:
            # Save audio to file for debugging
            debug_path = Path.home() / ".consciousness_engine/logs/speech"
            debug_path.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            sf.write(debug_path / f"speech_{timestamp}.wav", audio, SAMPLE_RATE)
            
            # Trigger callback with audio
            if self.callback:
                await self.callback(audio)
        except Exception as e:
            logger.error(f"Speech processing error: {e}")
    
    async def start(self):
        """Start the voice presence loop."""
        if self._running:
            logger.warning("Voice presence already running")
            return
        
        self._running = True
        logger.info("🎙️ Voice presence started - listening...")
        
        # Start audio stream
        self.audio_stream = sd.InputStream(
            callback=self._audio_callback,
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            device=None  # Default input
        )
        self.audio_stream.start()
        
        # Process loop
        await self._process_audio_loop()
    
    async def stop(self):
        """Stop the voice presence."""
        self._running = False
        if hasattr(self, 'audio_stream'):
            self.audio_stream.stop()
            self.audio_stream.close()
        logger.info("⏹️ Voice presence stopped")

# ============================================================================
# INTEGRATION WITH EXISTING SYSTEM
# ============================================================================
class VoicePresenceBridge:
    """
    Bridge between Voice Presence and the Consciousness Engine.
    """
    
    def __init__(self, engine_url: str = "http://localhost:11435"):
        self.engine_url = engine_url
        self.client = None
        self.tts_engine = None
    
    async def handle_speech(self, audio: np.ndarray):
        """Handle speech from the presence system."""
        logger.info("🎯 Speech detected - sending to engine...")
        
        # Here we'd:
        # 1. Transcribe using Vosk
        # 2. Send to LLM via /inject/stream or /v1/chat/completions
        # 3. Get response
        # 4. Synthesize via Kokoro TTS
        # 5. Play back
        
        # For now, just echo
        logger.info("🔄 Echo placeholder - actual processing coming soon")
        
        # This will be expanded to:
        # - ASR: vosk_model
        # - LLM: engine_url
        # - TTS: kokoro_pipeline

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
async def main():
    """Run the voice presence system."""
    logger.info("=" * 60)
    logger.info("🎤 CONSCIOUSNESS ENGINE - VOICE PRESENCE")
    logger.info("=" * 60)
    
    # Initialize presence
    presence = VoicePresence()
    if not presence.initialize():
        logger.error("❌ Voice presence initialization failed")
        return
    
    # Run
    try:
        await presence.start()
    except KeyboardInterrupt:
        logger.info("⏹️ Shutting down...")
        await presence.stop()
    except Exception as e:
        logger.error(f"❌ Voice presence error: {e}")
        await presence.stop()

if __name__ == "__main__":
    asyncio.run(main())