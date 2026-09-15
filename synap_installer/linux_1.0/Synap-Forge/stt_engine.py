#!/usr/bin/env python3
"""
Faster-Whisper STT Engine
High-performance Speech-to-Text for real-time voice interaction
"""

import numpy as np
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

# Try to import faster-whisper
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    logger.info("✅ faster-whisper available")
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("⚠️ faster-whisper not installed - STT unavailable")


@dataclass
class TranscriptionResult:
    """Result from STT transcription"""
    text: str
    segments: List[Dict[str, Any]]
    language: str
    duration: float
    confidence: float
    processing_time: float


class FasterWhisperSTT:
    """
    Faster-Whisper STT engine for real-time transcription
    
    Optimized for:
    - Real-time conversation (low latency)
    - Multiple model sizes (tiny → large-v3)
    - GPU acceleration (CUDA) or CPU
    """
    
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str = "en",
        beam_size: int = 1,
        vad_filter: bool = True,
        vad_parameters: Optional[Dict] = None,
    ):
        """
        Initialize the STT engine
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: 'cuda' or 'cpu'
            compute_type: 'float16', 'int8', 'float32'
            language: Language code (en, es, fr, etc.)
            beam_size: Beam size (1 = fastest)
            vad_filter: Enable Voice Activity Detection
            vad_parameters: VAD parameters dict
        """
        if not FASTER_WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper not installed")
        
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.vad_parameters = vad_parameters or {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 400,
        }
        
        # Load model
        logger.info(f"Loading faster-whisper model: {model_size} ({device}/{compute_type})")
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=4 if device == "cpu" else 0,
            num_workers=1,
        )
        logger.info(f"✅ STT model loaded: {model_size}")
        
        self._last_transcription = None
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        **kwargs
    ) -> Optional[TranscriptionResult]:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio as numpy array (float32, -1.0 to 1.0)
            sample_rate: Sample rate of audio (must match model)
            **kwargs: Additional parameters to pass to transcribe
            
        Returns:
            TranscriptionResult or None if failed
        """
        start_time = time.time()
        
        try:
            # Ensure audio is float32
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Transcribe
            segments, info = self.model.transcribe(
                audio_data,
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                vad_parameters=self.vad_parameters,
                **kwargs
            )
            
            # Collect results
            segment_list = []
            full_text = ""
            
            for segment in segments:
                segment_data = {
                    "text": segment.text,
                    "start": segment.start,
                    "end": segment.end,
                    "confidence": segment.avg_logprob,
                    "temperature": segment.temperature,
                }
                segment_list.append(segment_data)
                full_text += segment.text
            
            if not segment_list:
                return None
            
            result = TranscriptionResult(
                text=full_text.strip(),
                segments=segment_list,
                language=info.language,
                duration=info.duration,
                confidence=sum(s["confidence"] for s in segment_list) / len(segment_list),
                processing_time=time.time() - start_time,
            )
            
            self._last_transcription = result
            return result
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def transcribe_batch(
        self,
        audio_batches: List[np.ndarray],
        sample_rate: int = 16000,
    ) -> List[Optional[TranscriptionResult]]:
        """Transcribe multiple audio batches"""
        results = []
        for audio in audio_batches:
            result = self.transcribe(audio, sample_rate)
            results.append(result)
        return results
    
    def get_available_models(self) -> List[str]:
        """Get list of available Whisper model sizes"""
        return ["tiny", "base", "small", "medium", "large-v3"]
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get current model information"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "language": self.language,
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
            "available": FASTER_WHISPER_AVAILABLE,
        }


# ============================================================================
# CONVENIENCE FACTORY
# ============================================================================

def create_stt_engine(
    model_size: str = "small",
    device: str = "auto",
    **kwargs
) -> Optional[FasterWhisperSTT]:
    """
    Create an STT engine with automatic device detection
    
    Args:
        model_size: Whisper model size
        device: 'cuda', 'cpu', or 'auto'
        **kwargs: Additional arguments for FasterWhisperSTT
    """
    if not FASTER_WHISPER_AVAILABLE:
        logger.warning("faster-whisper not installed")
        return None
    
    # Auto-detect device
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    
    # Default compute type based on device
    if "compute_type" not in kwargs:
        kwargs["compute_type"] = "float16" if device == "cuda" else "int8"
    
    try:
        return FasterWhisperSTT(model_size=model_size, device=device, **kwargs)
    except Exception as e:
        logger.error(f"Failed to create STT engine: {e}")
        return None


# ============================================================================
# TEST / DEMO
# ============================================================================

if __name__ == "__main__":
    # Test STT engine
    print("🧪 Testing STT Engine...")
    
    engine = create_stt_engine("tiny", "cpu", compute_type="int8")
    if engine:
        print("✅ STT engine ready")
        print(f"   Model: {engine.model_size}")
        print(f"   Device: {engine.device}")
        print(f"   Compute: {engine.compute_type}")
    else:
        print("❌ STT engine failed to initialize")
        print("   Run: pip install faster-whisper")
