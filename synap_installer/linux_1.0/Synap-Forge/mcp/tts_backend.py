#!/usr/bin/env python3.12
"""
TTS Backend for Synap-Forge
Single instance, reused across all requests
"""

import os
import sys
import warnings
from io import BytesIO
from pathlib import Path

# Suppress warnings
os.environ["HF_TOKEN"] = "dummy"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
warnings.filterwarnings("ignore")

# Add kokoro path if needed
sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.12/site-packages"))

from kokoro import KPipeline
import soundfile as sf
import numpy as np

class KokoroBackend:
    """Singleton TTS backend for Synap-Forge"""
    
    _instance = None
    _pipeline = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the pipeline once"""
        print("🚀 Initializing Kokoro TTS Backend...")
        try:
            self._pipeline = KPipeline(lang_code='a', device='cpu')
            self._voice_path = os.path.expanduser("~/.cache/kokoro/voices/af_heart.pt")
            print("✅ Kokoro TTS Backend ready")
        except Exception as e:
            print(f"❌ Failed to initialize TTS: {e}")
            raise
    
    def synthesize(self, text: str, voice: str = None, speed: float = 1.0) -> bytes:
        """Synthesize speech from text, return WAV bytes"""
        if voice is None:
            voice = self._voice_path
        
        try:
            generator = self._pipeline(text, voice=voice, speed=speed)
            
            # Get first chunk (or stitch all chunks)
            all_audio = []
            for graphemes, phonemes, audio in generator:
                audio_np = audio.numpy() if hasattr(audio, 'numpy') else audio
                all_audio.append(audio_np)
                break  # Remove for multi-chunk stitching
            
            if not all_audio:
                raise RuntimeError("No audio generated")
            
            # Concatenate all chunks
            audio_out = np.concatenate(all_audio) if len(all_audio) > 1 else all_audio[0]
            
            # Write to bytes buffer
            buffer = BytesIO()
            sf.write(buffer, audio_out, 24000, format='WAV')
            return buffer.getvalue()
            
        except Exception as e:
            raise RuntimeError(f"TTS generation failed: {e}")
    
    def synthesize_to_file(self, text: str, output_path: str, voice: str = None, speed: float = 1.0):
        """Synthesize and save to file"""
        wav_bytes = self.synthesize(text, voice, speed)
        with open(output_path, 'wb') as f:
            f.write(wav_bytes)
        return output_path

# Global instance
tts = KokoroBackend()

# Test if run directly
if __name__ == "__main__":
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else "Hello, this is a test of the TTS backend."
    output = tts.synthesize_to_file(text, "/tmp/tts_test.wav")
    print(f"✅ Saved to: {output}")
