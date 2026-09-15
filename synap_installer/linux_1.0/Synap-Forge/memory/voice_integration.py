"""
Voice Integration - Faster Whisper STT + Kokoro TTS
====================================================
Fixed to use specific microphone device
"""

import os
import sys
import json
import queue
import time
import logging
import numpy as np
from typing import Callable, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False
    logger.warning("sounddevice not available")

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available")

try:
    from kokoro import KPipeline
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False
    logger.warning("Kokoro not available")


class VoiceEngine:
    """Voice engine using Faster Whisper + Kokoro"""
    
    def __init__(self, model_size: str = "base", device: str = "cpu", 
                 input_device: Optional[int] = None):
        """
        Args:
            model_size: tiny, base, small, medium
            device: cpu, cuda
            input_device: sounddevice device index (None = default)
        """
        self.sample_rate = 16000
        self.chunk_duration = 2.0
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.input_device = input_device
        
        # Find a working input device if none specified
        if self.input_device is None and SD_AVAILABLE:
            self.input_device = self._find_input_device()
        
        logger.info(f"🎤 Using input device: {self.input_device}")
        
        # Faster Whisper model
        self.whisper_model = None
        if WHISPER_AVAILABLE:
            try:
                self.whisper_model = WhisperModel(
                    model_size, 
                    device=device, 
                    compute_type="int8",
                    cpu_threads=4,
                    num_workers=1
                )
                logger.info(f"✅ Faster Whisper loaded: {model_size} on {device}")
            except Exception as e:
                logger.error(f"Faster Whisper init failed: {e}")
        
        # Kokoro TTS
        self.tts_pipeline = None
        if KOKORO_AVAILABLE:
            try:
                self.tts_pipeline = KPipeline(lang_code='a')
                self.tts_voice = 'af_heart'
                self.tts_speed = 1.0
                logger.info("✅ Kokoro TTS ready")
            except Exception as e:
                logger.warning(f"Kokoro init failed: {e}")
        
        if not self.whisper_model:
            logger.warning("⚠️  No STT model - speech recognition disabled")
        
        logger.info("✅ VoiceEngine initialized")
    
    def _find_input_device(self) -> Optional[int]:
        """Find a working input device"""
        try:
            devices = sd.query_devices()
            
            # Look for devices with input channels > 0
            candidates = []
            for i, dev in enumerate(devices):
                if dev.get('max_input_channels', 0) > 0:
                    candidates.append((i, dev.get('name', '')))
            
            logger.info(f"Found {len(candidates)} input devices")
            
            # Prefer specific names
            preferred = ['ALC233', 'Analog', 'Speaker', 'microphone', 'Mic']
            for pref in preferred:
                for idx, name in candidates:
                    if pref.lower() in name.lower():
                        logger.info(f"✅ Selected device {idx}: {name}")
                        return idx
            
            # Fallback to first input device
            if candidates:
                idx, name = candidates[0]
                logger.info(f"✅ Using first input device {idx}: {name}")
                return idx
            
            return None
        except Exception as e:
            logger.error(f"Device detection failed: {e}")
            return None
    
    def listen(self, callback: Callable[[str], None], duration: float = 10.0):
        """Listen and transcribe with Faster Whisper"""
        if not self.whisper_model or not SD_AVAILABLE:
            logger.error("Voice input not available")
            return
        
        if self.input_device is None and SD_AVAILABLE:
            logger.error("No input device found")
            return
        
        audio_buffer = []
        self.is_listening = True
        
        def audio_callback(indata, frames, time, status):
            if status:
                logger.debug(f"Audio status: {status}")
            self.audio_queue.put(indata.copy())
        
        def process_audio():
            audio_chunks = []
            start_time = time.time()
            silence_counter = 0
            
            while self.is_listening:
                try:
                    chunk = self.audio_queue.get(timeout=0.5)
                    audio_chunks.append(chunk)
                    
                    total_samples = sum(len(c) for c in audio_chunks)
                    total_seconds = total_samples / self.sample_rate
                    
                    if total_seconds >= self.chunk_duration:
                        audio_data = np.concatenate(audio_chunks)
                        audio_float = audio_data.astype(np.float32) / 32768.0
                        
                        try:
                            segments, info = self.whisper_model.transcribe(
                                audio_float,
                                language="en",
                                beam_size=5,
                                vad_filter=True,
                                vad_parameters={
                                    "threshold": 0.5,
                                    "min_speech_duration_ms": 250,
                                    "min_silence_duration_ms": 500,
                                }
                            )
                            
                            text_parts = []
                            for segment in segments:
                                text_parts.append(segment.text)
                            
                            if text_parts:
                                full_text = " ".join(text_parts).strip()
                                if len(full_text) > 3:
                                    logger.info(f"🎤 Heard: {full_text}")
                                    callback(full_text)
                        except Exception as e:
                            logger.debug(f"Transcription error: {e}")
                        
                        audio_chunks = []
                        silence_counter = 0
                    
                    if not self.audio_queue.empty():
                        silence_counter = 0
                    else:
                        silence_counter += 1
                        
                    if silence_counter > 10 and len(audio_chunks) > 0:
                        audio_data = np.concatenate(audio_chunks)
                        audio_float = audio_data.astype(np.float32) / 32768.0
                        try:
                            segments, info = self.whisper_model.transcribe(
                                audio_float,
                                language="en",
                                beam_size=5
                            )
                            text_parts = []
                            for segment in segments:
                                text_parts.append(segment.text)
                            if text_parts:
                                full_text = " ".join(text_parts).strip()
                                if len(full_text) > 3:
                                    logger.info(f"🎤 Heard: {full_text}")
                                    callback(full_text)
                        except:
                            pass
                        audio_chunks = []
                        silence_counter = 0
                        
                except queue.Empty:
                    pass
                
                if duration > 0 and (time.time() - start_time) > duration:
                    break
        
        # Start stream with specific device
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='int16',
            callback=audio_callback,
            blocksize=int(self.sample_rate * 0.5),
            device=self.input_device  # Explicit device
        )
        
        with stream:
            logger.info(f"🎤 Listening on device {self.input_device}...")
            process_audio()
        
        self.is_listening = False
        logger.info("🎤 Stopped listening")
    
    def speak(self, text: str):
        """Speak using Kokoro TTS"""
        if not text:
            return
        
        logger.info(f"🗣️ Speaking: {text[:100]}...")
        
        if self.tts_pipeline:
            try:
                audio_chunks = []
                for _, _, audio in self.tts_pipeline(
                    text,
                    voice=self.tts_voice,
                    speed=self.tts_speed
                ):
                    if audio is not None and len(audio) > 0:
                        audio_chunks.append(audio)
                
                if audio_chunks:
                    audio = np.concatenate(audio_chunks)
                    if SD_AVAILABLE:
                        sd.play(audio, samplerate=24000)
                        sd.wait()
                    else:
                        logger.info(f"[TTS] {text}")
                else:
                    print(f"[TTS Fallback] {text}")
            except Exception as e:
                logger.error(f"TTS error: {e}")
                print(f"[TTS Error] {text}")
        else:
            print(f"[TTS] {text}")


class VoiceMemoryIntegration:
    """Bridge between voice and memory"""
    
    def __init__(self, memory_system, whisper_model: str = "base", 
                 device: str = "cpu", input_device: Optional[int] = None):
        self.memory = memory_system
        self.voice = VoiceEngine(
            model_size=whisper_model, 
            device=device,
            input_device=input_device
        )
        self.conversation_active = False
    
    def process_text(self, text: str) -> str:
        """Process through memory"""
        if not text or not text.strip():
            return "I didn't catch that."
        
        if hasattr(self.memory, 'ingest'):
            self.memory.ingest(text, "voice_user")
        
        try:
            if hasattr(self.memory, 'recall'):
                result = self.memory.recall(text, limit=3)
                context = result.get('context', '')
                
                if context:
                    return f"{context[:200]}"
                else:
                    return f"I hear you: {text[:80]}..."
            else:
                return f"You said: {text}"
        except Exception as e:
            logger.error(f"Memory error: {e}")
            return "Processing..."
    
    def start_conversation(self):
        """Start voice loop"""
        self.conversation_active = True
        self.voice.speak("I'm here. What's on your mind?")
        
        def on_speech(text):
            if not self.conversation_active:
                return
            if "goodbye" in text.lower() or "exit" in text.lower():
                self.voice.speak("Talk to you soon.")
                self.conversation_active = False
                return
            response = self.process_text(text)
            self.voice.speak(response)
        
        while self.conversation_active:
            try:
                self.voice.listen(on_speech, duration=10.0)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Voice loop error: {e}")
                time.sleep(1)
        
        self.conversation_active = False
    
    def stop(self):
        self.conversation_active = False


