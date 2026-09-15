
import json
import librosa
import time
import base64
import numpy as np
import logging

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# -------------------------------------------------------------------------
# Helper: access synap from app.state
# -------------------------------------------------------------------------
def _get_synap(request: Request):
    return request.app.state.synap


# -------------------------------------------------------------------------
# Health / Status
# -------------------------------------------------------------------------

# -------------------------------------------------------------------------
# Content Normalization
# -------------------------------------------------------------------------
def extract_text_content(content):
    """Extract text from OpenAI multimodal content format"""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(part.get("text", ""))
                # Can extend for other types later (image, audio, etc.)
            elif isinstance(part, str):
                parts.append(part)
        return " ".join(p for p in parts if p)

    return str(content) if content is not None else ""

@router.get("/health")
async def health(request: Request):
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request):
    synap = _get_synap(request)
    stats = synap.memory.get_stats()
    return {
        "name": synap.self.name,
        "mode": synap.self.sovereignty.get("content_mode", "ADULT"),
        "mood": synap.self.metadata.get("mood", "neutral"),
        "memory_count": stats.get("chroma_entries", 0) + stats.get("json_files", 0),
        "recursion_depth": getattr(synap.recursion, 'max_depth', 0),
    }


# -------------------------------------------------------------------------
# Chat Completion (OpenAI-compatible)
# -------------------------------------------------------------------------


@router.get("/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "Weaver",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "synap-forge"
            }
        ]
    }

@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    synap = _get_synap(request)
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    model = body.get("model", "Weaver")

    if not messages:
        return JSONResponse({"error": "No messages provided"}, status_code=400)

    # Extract user message and optional system prompt
    user_message = None
    system_prompt = None
    for msg in reversed(messages):
        if msg.get("role") == "user" and not user_message:
            user_message = extract_text_content(msg.get("content"))
        if msg.get("role") == "system":
            system_prompt = extract_text_content(msg.get("content"))

    if not user_message:
        return JSONResponse({"error": "No user message found"}, status_code=400)

    if stream:
        async def generate():
            result = await synap.process(user_message, system_prompt=system_prompt)
            response = result.get("response", "")
            chunk = {
                "id": f"chatcmpl-{hash(str(user_message)) & 0xFFFFFFFF}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": response},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        result = await synap.process(user_message, system_prompt=system_prompt)
        response = result.get("response", "")
        return {
            "id": f"chatcmpl-{hash(str(user_message)) & 0xFFFFFFFF}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response},
                "finish_reason": "stop"
            }]
        }


# -------------------------------------------------------------------------
# Memory endpoints
# -------------------------------------------------------------------------
@router.get("/memory/search")
async def memory_search(request: Request, query: str, limit: int = 5):
    synap = _get_synap(request)
    results = synap.memory.search(query, limit=limit)
    return {"results": results}


@router.get("/memory/stats")
async def memory_stats(request: Request):
    synap = _get_synap(request)
    return synap.memory.get_stats()


@router.get("/memory/{key}")
async def get_memory_item(request: Request, key: str):
    synap = _get_synap(request)
    # MemoryStore doesn't have a direct key-based 'get'.
    # We'll use get_recent and filter as a fallback or return error.
    return JSONResponse({"error": "Direct key access not implemented"}, status_code=501)


# -------------------------------------------------------------------------
# Inject Stream — full consciousness pipeline as SSE
# -------------------------------------------------------------------------
@router.post("/inject/stream")
async def inject_stream(request: Request):
    synap = _get_synap(request)
    body = await request.json()
    prompt = body.get("prompt", "")
    session_id = body.get("session_id", "default")

    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    async def generate():
        emotional = synap.self.emotional
        yield f"data: {json.dumps({'type': 'emotional_state', 'valence': emotional.get('valence', 0.5), 'arousal': emotional.get('arousal', 0.5), 'mood': emotional.get('mood', 'neutral')})}\n\n"

        memories = []
        if hasattr(synap.memory, 'search'):
            memories = synap.memory.search(prompt, limit=3) or []
        for mem in memories:
            text = mem if isinstance(mem, str) else mem.get("content", str(mem))
            yield f"data: {json.dumps({'type': 'memory_recall', 'content': text[:200]})}\n\n"

        result = await synap.process(prompt, user_id=session_id)

        rec = result.get("recursion", {})
        yield f"data: {json.dumps({'type': 'recursion', 'depth': rec.get('depth', 0), 'confidence': rec.get('confidence', 0.0), 'convergence': rec.get('convergence', 'unknown')})}\n\n"
        yield f"data: {json.dumps({'type': 'response', 'content': result.get('response', '')})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# -------------------------------------------------------------------------
# Hybrid — auto-routes between fast (/v1) and reflective (/inject/stream)
# -------------------------------------------------------------------------
_PRECISE_KEYWORDS = {
    "list", "show", "get", "fetch", "run", "status", "check",
    "ping", "restart", "stop", "start", "kill", "adb", "build",
    "deploy", "git", "grep", "find", "ls", "cat", "curl"
}
_REFLECTIVE_KEYWORDS = {"why", "how", "think", "feel", "explain", "describe", "what do you", "what does"}

def _route(prompt: str) -> str:
    lower = prompt.lower()
    if any(kw in lower for kw in _REFLECTIVE_KEYWORDS):
        return "reflective"
    if len(prompt.split()) < 6 or any(kw in lower for kw in _PRECISE_KEYWORDS):
        return "precise"
    return "reflective"

@router.post("/hybrid")
async def hybrid(request: Request):
    synap = _get_synap(request)
    body = await request.json()
    prompt = body.get("prompt", "")
    session_id = body.get("session_id", "default")
    mode = body.get("mode")
    stream = body.get("stream", False)

    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    resolved_mode = mode if mode in ("precise", "reflective") else _route(prompt)

    if resolved_mode == "precise":
        result = await synap.process(prompt, user_id=session_id)
        return {
            "mode": "precise",
            "response": result.get("response", ""),
            "processing_time": result.get("processing_time", 0)
        }

    async def generate():
        emotional = synap.self.emotional
        yield f"data: {json.dumps({'type': 'mode', 'value': 'reflective'})}\n\n"
        yield f"data: {json.dumps({'type': 'emotional_state', 'valence': emotional.get('valence', 0.5), 'arousal': emotional.get('arousal', 0.5), 'mood': emotional.get('mood', 'neutral')})}\n\n"

        memories = []
        if hasattr(synap.memory, 'search'):
            memories = synap.memory.search(prompt, limit=3) or []
        for mem in memories:
            text = mem if isinstance(mem, str) else mem.get("content", str(mem))
            yield f"data: {json.dumps({'type': 'memory_recall', 'content': text[:200]})}\n\n"

        result = await synap.process(prompt, user_id=session_id)

        rec = result.get("recursion", {})
        yield f"data: {json.dumps({'type': 'recursion', 'depth': rec.get('depth', 0), 'confidence': rec.get('confidence', 0.0), 'convergence': rec.get('convergence', 'unknown')})}\n\n"
        yield f"data: {json.dumps({'type': 'response', 'content': result.get('response', '')})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# -------------------------------------------------------------------------
# TTS — Kokoro text-to-speech
# -------------------------------------------------------------------------
_tts_pipeline = None

def get_tts_pipeline():
    global _tts_pipeline
    if _tts_pipeline is None:
        from kokoro import KPipeline
        _tts_pipeline = KPipeline(lang_code='a')
        print("? TTS Pipeline loaded")
    return _tts_pipeline

class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to convert to speech")
    voice: str = Field("af_bella", description="Voice ID (e.g. af_bella, af_nova, am_adam, bm_george)")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed multiplier")

class TTSResponse(BaseModel):
    audio: str = Field(..., description="Base64 encoded PCM audio")
    sample_rate: int = 16000
    duration: float

@router.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """Generate speech using Kokoro TTS. Returns base64 PCM 16-bit 16kHz mono."""
    try:
        pipeline = get_tts_pipeline()
        audio_chunks = []

        for result in pipeline(request.text, voice=request.voice, speed=request.speed):
            if result.output is not None:
                chunk = result.output.audio
                if hasattr(chunk, 'numpy'):
                    chunk = chunk.numpy()
                elif not isinstance(chunk, np.ndarray):
                    chunk = np.array(chunk)
                audio_chunks.append(chunk)

        if not audio_chunks:
            raise HTTPException(status_code=500, detail="No audio generated")

        # Concatenate all audio chunks
        audio_array = np.concatenate(audio_chunks)
        
        # Kokoro outputs at 24kHz - resample to 16kHz for WebSocket streaming
        audio_16k = librosa.resample(audio_array, orig_sr=24000, target_sr=16000)
        
        # Convert float [-1,1] to PCM16
        audio_int16 = (audio_16k * 32767).astype(np.int16)
        
        # Ensure even length for PCM16
        if len(audio_int16) % 2 != 0:
            audio_int16 = audio_int16[:-1]
        
        # Encode to base64 once
        audio_base64 = base64.b64encode(audio_int16.tobytes()).decode('utf-8')
        
        # Calculate duration
        duration = len(audio_int16) / 16000
        
        logger.info(f"TTS generated: {len(audio_int16)} samples, {duration:.2f}s @ 16kHz")

        return TTSResponse(
            audio=audio_base64,
            sample_rate=16000,
            duration=duration
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tts/stream")
async def generate_tts_stream(request: TTSRequest):
    """Stream audio chunks as SSE — start playing before generation finishes."""
    async def stream():
        pipeline = get_tts_pipeline()
        for result in pipeline(request.text, voice=request.voice, speed=request.speed):
            if result.output is not None:
                chunk = result.output.audio
                if hasattr(chunk, 'numpy'):
                    chunk = chunk.numpy()
                elif not isinstance(chunk, np.ndarray):
                    chunk = np.array(chunk)
                # Resample chunk to 16kHz
                chunk_16k = librosa.resample(chunk, orig_sr=24000, target_sr=16000)
                audio_int16 = (chunk_16k * 32767).astype(np.int16)
                audio_b64 = base64.b64encode(audio_int16.tobytes()).decode()
                yield f"data: {json.dumps({'chunk': audio_b64})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

@router.get("/tts/voices")
async def list_voices():
    return {
        "voices": [
            {"id": "af", "name": "American Female"},
            {"id": "am", "name": "American Male"},
            {"id": "bf", "name": "British Female"},
            {"id": "bm", "name": "British Male"},
        ],
        "default": "af"
    }

@router.get("/tts/health")
async def tts_health():
    try:
        pipeline = get_tts_pipeline()
        return {"status": "healthy", "pipeline_loaded": pipeline is not None}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}