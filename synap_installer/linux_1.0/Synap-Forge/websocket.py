#!/usr/bin/env python3
# websocket.py - Fixed WebSocket handler for Synap-Forge

import json
import asyncio
import uuid
import time
import logging
import base64
import binascii
from typing import Dict, Any, Optional, AsyncGenerator, List, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================
# WebSocket Message Types
# ============================================================

class MessageType(Enum):
    TEXT = "text_message"
    THOUGHT = "thought"
    ASSISTANT = "assistant"
    ASSISTANT_CHUNK = "assistant_chunk"
    STATUS = "status"
    ERROR = "error"
    TOOL_EXECUTION = "tool_execution"
    MEMORY_RECALL = "memory_recall"
    SYSTEM_STATE = "system_state"
    DONE = "done"
    HANDSHAKE = "handshake_ack"

@dataclass
class WebSocketMessage:
    type: str
    content: Any
    timestamp: float = None
    message_id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())[:8]
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))

@dataclass
class AudioMessage:
    """Audio frame message for WebSocket"""
    type: str = "audio_frame"
    format: str = "S16_LE"
    sample_rate: int = 16000
    channels: int = 1
    data: str = ""  # Base64 encoded audio data
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))

# ============================================================
# Connection Manager
# ============================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.audio_streams: Dict[str, bool] = {}
        self.bridge_state: Dict[str, bool] = {}
        self.tts_tasks: Dict[str, Set[asyncio.Task]] = {}
        self.opus_decoders: Dict[str, Any] = {}
        self.audio_locks: Dict[str, asyncio.Lock] = {}
        self.audio_tasks: Dict[str, asyncio.Task] = {}
        self.tts_queues: Dict[str, asyncio.Queue] = {}
        self.tts_workers: Dict[str, asyncio.Task] = {}
        self.stream_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str = None):
        await websocket.accept()
        if session_id is None:
            session_id = str(uuid.uuid4())
        self.active_connections[session_id] = websocket
        self.sessions[session_id] = {
            "connected_at": time.time(),
            "message_count": 0,
            "last_activity": time.time()
        }
        self.audio_streams[session_id] = False
        self.bridge_state[session_id] = False
        self.tts_tasks[session_id] = set()
        self.audio_locks[session_id] = asyncio.Lock()
        self.tts_queues[session_id] = asyncio.Queue()
        # Start TTS worker for this session
        self.tts_workers[session_id] = asyncio.create_task(
            self._tts_worker(session_id)
        )
        logger.info(f"🔌 WebSocket connected: {session_id} (Total: {len(self.active_connections)})")
        return session_id
    
    def disconnect(self, session_id: str):
        existed = session_id in self.active_connections
        
        # Cancel all TTS tasks for this session
        if session_id in self.tts_tasks:
            for task in self.tts_tasks[session_id]:
                if not task.done():
                    task.cancel()
            del self.tts_tasks[session_id]
        
        # Cancel TTS worker
        if session_id in self.tts_workers:
            worker = self.tts_workers[session_id]
            if not worker.done():
                worker.cancel()
            del self.tts_workers[session_id]
        
        # Clear TTS queue
        if session_id in self.tts_queues:
            del self.tts_queues[session_id]
        
        # Cancel active LLM stream task
        task = self.stream_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
        
        # Cancel audio processing task
        audio_task = self.audio_tasks.pop(session_id, None)
        if audio_task and not audio_task.done():
            audio_task.cancel()
        
        # Clear audio buffer for this session
        _audio_buffers.pop(session_id, None)
        
        # Clear Opus decoder
        if session_id in self.opus_decoders:
            del self.opus_decoders[session_id]
        
        # Clear audio lock
        if session_id in self.audio_locks:
            del self.audio_locks[session_id]
        
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.audio_streams:
            del self.audio_streams[session_id]
        if session_id in self.bridge_state:
            del self.bridge_state[session_id]
        
        if existed:
            logger.info(f"🔌 WebSocket disconnected: {session_id} (Total: {len(self.active_connections)})")
    
    def track_tts_task(self, session_id: str, task: asyncio.Task):
        """Track a TTS task for cancellation on disconnect"""
        if session_id not in self.tts_tasks:
            self.tts_tasks[session_id] = set()
        self.tts_tasks[session_id].add(task)
        # Use .get() to avoid KeyError if session is disconnected during cleanup
        task.add_done_callback(
            lambda t: self.tts_tasks.get(session_id, set()).discard(t)
        )
    
    async def _tts_worker(self, session_id: str):
        """Per-session TTS worker that processes sentences in order"""
        import requests
        import base64
        
        while True:
            try:
                # Get next sentence from queue
                text = await self.tts_queues[session_id].get()
                
                # Check if session still exists
                if session_id not in self.active_connections:
                    logger.info(f"🔌 Session {session_id} gone, stopping TTS worker")
                    break
                
                # Generate and send TTS
                try:
                    def _call_tts():
                        return requests.post(
                            "http://localhost:11436/tts",
                            json={"text": text, "voice": "af_bella", "speed": 1.0},
                            timeout=60
                        )
                    
                    response = await asyncio.to_thread(_call_tts)
                    
                    if session_id not in self.active_connections:
                        logger.info(f"🔌 Session {session_id} disconnected during TTS generation")
                        break
                    
                    if response.status_code == 200:
                        data = response.json()
                        audio_b64 = data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            frame_size = 640
                            total_sent = 0
                            for i in range(0, len(audio_bytes), frame_size):
                                if session_id not in self.active_connections:
                                    logger.info(f"🔌 Session {session_id} disconnected during TTS send")
                                    break
                                chunk = audio_bytes[i:i+frame_size]
                                if len(chunk) < frame_size:
                                    chunk = chunk + b'\x00' * (frame_size - len(chunk))
                                if not await self.send_audio(session_id, chunk):
                                    break
                                total_sent += len(chunk)
                                await asyncio.sleep(0.005)
                            if total_sent > 0:
                                logger.info(f"🔊 TTS audio sent to {session_id}: {total_sent} bytes in chunks")
                    else:
                        logger.error(f"TTS HTTP error: {response.status_code}")
                except Exception as e:
                    logger.error(f"TTS generation error: {e}")
                
                self.tts_queues[session_id].task_done()
                
            except asyncio.CancelledError:
                logger.info(f"🛑 TTS worker cancelled for {session_id}")
                break
            except Exception as e:
                logger.error(f"TTS worker error: {e}")
                await asyncio.sleep(0.1)
    
    def queue_tts(self, session_id: str, text: str):
        """Queue a sentence for TTS processing"""
        if session_id in self.tts_queues:
            self.tts_queues[session_id].put_nowait(text)
    
    async def send_message(self, session_id: str, message: WebSocketMessage, increment_count: bool = True):
        if session_id not in self.active_connections:
            return False
        
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        try:
            await self.active_connections[session_id].send_text(message.to_json())
            session["last_activity"] = time.time()
            if increment_count:
                session["message_count"] += 1
            return True
        except Exception as e:
            logger.error(f"Failed to send to {session_id}: {e}")
            return False
    
    async def send_audio(self, session_id: str, audio_data: bytes, format: str = "S16_LE", sample_rate: int = 16000):
        """Send audio as binary frame"""
        if session_id not in self.active_connections:
            return False
        if not self.audio_streams.get(session_id, False):
            return False
        try:
            await self.active_connections[session_id].send_bytes(audio_data)
            session = self.sessions.get(session_id)
            if session:
                session["last_activity"] = time.time()
            logger.debug(f"🎵 Sent audio: {len(audio_data)} bytes to {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send audio to {session_id}: {e}")
            self.disconnect(session_id)
            return False
    
    async def broadcast_audio(self, audio_data: bytes, exclude: str = None, format: str = "S16_LE"):
        """Broadcast audio to all connected clients with audio enabled"""
        for session_id in self.active_connections:
            if session_id != exclude and self.audio_streams.get(session_id, False):
                await self.send_audio(session_id, audio_data, format)
    
    async def broadcast(self, message: WebSocketMessage, exclude: str = None):
        for session_id, websocket in self.active_connections.items():
            if session_id != exclude:
                try:
                    await websocket.send_text(message.to_json())
                except Exception as e:
                    logger.error(f"Broadcast failed to {session_id}: {e}")

manager = ConnectionManager()

# ============================================================
# Whisper STT — lazy singleton with lock for thread safety
# ============================================================
_whisper_model = None
_whisper_lock = asyncio.Lock()

async def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        async with _whisper_lock:
            if _whisper_model is None:
                from faster_whisper import WhisperModel
                logger.info("Loading Whisper tiny model for low latency...")
                _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
                logger.info("✅ Whisper tiny loaded")
    return _whisper_model

# ============================================================
# Helper Functions
# ============================================================

_audio_buffers: Dict[str, list] = {}
_ACCUMULATE_FRAMES = 50  # ~1 second at 20ms per frame

# Audio codec constants - must match Android client
CODEC_PCM16 = 0
CODEC_OPUS = 1

async def handle_incoming_audio(session_id: str, audio_bytes: bytes, synap):
    """STT -> consciousness -> TTS pipeline for incoming audio frames"""
    try:
        import numpy as np

        # Strip 5-byte Lyra header (4-byte seq LE + 1-byte codec)
        if len(audio_bytes) < 5:
            # Try to detect raw Opus (no header)
            try:
                import opuslib
                opuslib.Decoder(16000, 1).decode(audio_bytes, 320)
                # It worked! Treat as raw Opus
                codec = CODEC_OPUS
                payload = audio_bytes
            except:
                return
            return
        codec = audio_bytes[4]
        payload = audio_bytes[5:]

        # Decode to PCM float32 based on codec
        async with manager.audio_locks.get(session_id, asyncio.Lock()):
            if codec == CODEC_OPUS:
                # Opus at 16kHz mono
                import opuslib
                if session_id not in manager.opus_decoders:
                    manager.opus_decoders[session_id] = opuslib.Decoder(16000, 1)
                decoder = manager.opus_decoders[session_id]
                pcm_bytes = decoder.decode(payload, 320)
                audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            elif codec == CODEC_PCM16:
                # Raw PCM S16_LE
                if len(payload) % 2 != 0:
                    payload = payload[:-1]
                audio_np = np.frombuffer(payload, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                logger.warning(f"Unknown audio codec {codec} from {session_id}")
                return

        if audio_np.size == 0:
            return

        # Accumulate frames — Whisper needs at least ~1s to transcribe reliably
        if session_id not in _audio_buffers:
            _audio_buffers[session_id] = []
        _audio_buffers[session_id].append(audio_np)

        if len(_audio_buffers[session_id]) < _ACCUMULATE_FRAMES:
            return

        full_audio = np.concatenate(_audio_buffers[session_id])
        _audio_buffers[session_id] = []

        logger.info(f"🎤 Processing {len(full_audio)} samples from {session_id}")
        
        # Send status to keep client alive during processing
        await manager.send_message(session_id, WebSocketMessage(
            type=MessageType.STATUS.value,
            content={"state": "listening", "message": "🎤 Processing audio..."}
        ), increment_count=False)

        # Already 16kHz from Android — no resample needed
        audio_16k = full_audio

        # STT - FAST with beam_size=1 for minimum latency
        whisper = await get_whisper()
        segments, _ = await asyncio.to_thread(
            whisper.transcribe, audio_16k, beam_size=1, language="en"
        )
        text = " ".join(seg.text for seg in segments).strip()

        if not text:
            logger.debug(f"🎤 No speech detected from {session_id}")
            return

        logger.info(f"🎤 Transcribed [{session_id}]: {text}")

        # Consciousness pipeline - use streaming (move off receive loop)
        asyncio.create_task(
            handle_chat_message(session_id, text, {"user_id": session_id}, synap)
        )

    except Exception as e:
        logger.error(f"Audio pipeline error [{session_id}]: {e}")

async def handle_chat_message(session_id: str, content: str, raw_message: dict, synap):
    """Stream tokens -> sentence TTS pipeline"""
    # Cancel any in-flight response for this session
    current_task = manager.stream_tasks.get(session_id)
    if current_task and not current_task.done():
        current_task.cancel()

    task = asyncio.create_task(
        _stream_chat(session_id, content, raw_message, synap)
    )
    manager.stream_tasks[session_id] = task
    try:
        await task
    except asyncio.CancelledError:
        logger.info(f"🛑 Stream cancelled for {session_id}")
    finally:
        if manager.stream_tasks.get(session_id) is task:
            manager.stream_tasks.pop(session_id, None)

async def _stream_chat(session_id: str, content: str, raw_message: dict, synap):
    """Inner streaming handler"""
    try:
        await manager.send_message(session_id, WebSocketMessage(
            type=MessageType.STATUS.value,
            content={"state": "thinking", "message": "🧠 Thinking..."}
        ), increment_count=False)

        user_id = raw_message.get("user_id", session_id)
        audio_enabled = manager.audio_streams.get(session_id, False)

        sentence_buf = ""
        sentence_ends = set(".!?")
        full_response = ""

        # Check for stream_process - test the actual returned object
        streamer = getattr(synap, "stream_process", None)
        if streamer:
            stream_result = streamer(content, user_id=user_id)
            if hasattr(stream_result, "__aiter__"):
                async for token in stream_result:
                    # Check if session still exists
                    if session_id not in manager.active_connections:
                        logger.info(f"🔌 Session {session_id} disconnected during streaming")
                        return
                    
                    full_response += token
                    sentence_buf += token

                    # Send token to app immediately
                    await manager.send_message(session_id, WebSocketMessage(
                        type=MessageType.ASSISTANT_CHUNK.value,
                        content=token
                    ), increment_count=False)

                    # TTS at sentence boundaries - queue for ordered playback
                    if audio_enabled and sentence_buf.strip() and sentence_buf[-1] in sentence_ends:
                        sentence = sentence_buf.strip()
                        sentence_buf = ""
                        manager.queue_tts(session_id, sentence)
            else:
                # Fallback: non-streaming if stream_process didn't return async iterable
                result = await synap.process(content, user_id=user_id)
                full_response = result.get("response", "")
                await manager.send_message(session_id, WebSocketMessage(
                    type=MessageType.ASSISTANT.value,
                    content=full_response
                ), increment_count=False)
                if audio_enabled:
                    manager.queue_tts(session_id, full_response)
        else:
            # No stream_process method - use regular process
            result = await synap.process(content, user_id=user_id)
            full_response = result.get("response", "")
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.ASSISTANT.value,
                content=full_response
            ), increment_count=False)
            if audio_enabled:
                manager.queue_tts(session_id, full_response)

        # Flush any remaining sentence fragment
        if audio_enabled and sentence_buf.strip():
            manager.queue_tts(session_id, sentence_buf.strip())

        await manager.send_message(session_id, WebSocketMessage(
            type=MessageType.DONE.value,
            content={"reason": "response_complete"}
        ), increment_count=False)

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Chat handler error: {e}")
        await manager.send_message(session_id, WebSocketMessage(
            type=MessageType.ERROR.value,
            content=str(e)
        ), increment_count=False)

async def execute_tool(tool_name: str, params: dict) -> dict:
    return {"status": "success", "result": f"Executed {tool_name} with {params}"}

async def generate_random_thought(context: str) -> dict:
    return {"text": "A random thought wanders through...", "confidence": 0.5, "valence": 0.5, "arousal": 0.5}

async def get_system_status() -> dict:
    return {
        "mcp_gateway": "online",
        "adb": "ready",
        "memory": "connected",
        "model": "fallback",
        "tools": 12,
        "connections": len(manager.active_connections)
    }

# ============================================================
# WebSocket Endpoint
# ============================================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket handler for Synap-Forge Studio"""
    
    synap = websocket.app.state.synap
    session_id = await manager.connect(websocket)
    
    await manager.send_message(session_id, WebSocketMessage(
        type=MessageType.STATUS.value,
        content={
            "message": "Connected to Synap-Forge Studio",
            "session_id": session_id,
            "version": "1.0.0",
            "features": ["chat", "tools", "memory", "streaming", "audio"]
        }
    ), increment_count=False)
    
    try:
        while True:
            try:
                message = await websocket.receive()
                
                if message["type"] == "websocket.receive":
                    if "text" in message:
                        data = message["text"]
                        await handle_text_message(session_id, data, synap, websocket)
                    elif "bytes" in message:
                        audio_data = message["bytes"]
                        if manager.bridge_state.get(session_id, False):
                            # Auto-detect raw browser Opus (WebM/Opus)
                            if len(audio_data) > 4 and audio_data[0:4] != b'\x00\x00\x00\x00':
                                # Wrap with header: seq=0, codec=Opus (1)
                                header = b'\x00\x00\x00\x00\x01'
                                audio_data = header + audio_data
                            current_audio_task = manager.audio_tasks.get(session_id)
                            if current_audio_task and not current_audio_task.done():
                                current_audio_task.cancel()
                            manager.audio_tasks[session_id] = asyncio.create_task(
                                handle_incoming_audio(session_id, audio_data, synap)
                            )
                        else:
                            logger.debug(f"Bridge off, audio frame ignored from {session_id}")
                        audio_data = message["bytes"]
                        if manager.bridge_state.get(session_id, False):
                            # Use a single audio task per session to prevent accumulation
                            current_audio_task = manager.audio_tasks.get(session_id)
                            if current_audio_task and not current_audio_task.done():
                                # Cancel previous audio processing if still running
                                current_audio_task.cancel()
                            # Start new audio processing task
                            manager.audio_tasks[session_id] = asyncio.create_task(
                                handle_incoming_audio(session_id, audio_data, synap)
                            )
                        else:
                            logger.debug(f"Bridge off, audio frame ignored from {session_id}")
                            
            except WebSocketDisconnect:
                manager.disconnect(session_id)
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(session_id)

async def handle_text_message(session_id: str, data: str, synap, websocket):
    """Handle text/JSON messages"""
    try:
        message = json.loads(data)
        message_type = message.get("type", "text_message")
        content = message.get("content", "")
        
        session = manager.sessions.get(session_id)
        if session:
            session["last_activity"] = time.time()
            # Only increment for actual user messages, not system acks
            if message_type in ("text_message", "chat", "audio_frame"):
                session["message_count"] += 1
        
        if message_type == "audio_control":
            enable = message.get("enable", False)
            manager.audio_streams[session_id] = enable
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.STATUS.value,
                content={
                    "type": "audio_status",
                    "streaming": enable,
                    "sample_rate": 16000,
                    "format": "S16_LE"
                }
            ), increment_count=False)
            logger.info(f"🎵 Audio streaming {'enabled' if enable else 'disabled'} for {session_id}")
        
        elif message_type == "barge_in":
            # Cancel current response and clear audio buffer
            current_task = manager.stream_tasks.get(session_id)
            if current_task and not current_task.done():
                current_task.cancel()
            _audio_buffers.pop(session_id, None)
            logger.info(f"🛑 Barge-in from {session_id}")

        elif message_type == "bridge_toggle":
            active = message.get("active", False)
            manager.bridge_state[session_id] = active
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.STATUS.value,
                content={
                    "type": "bridge_status",
                    "active": active,
                    "timestamp": time.time()
                }
            ), increment_count=False)
            logger.info(f"🌉 Bridge {'activated' if active else 'deactivated'} for {session_id}")
        
        elif message_type == "audio_frame":
            audio_b64 = message.get("data", "")
            if audio_b64 and manager.bridge_state.get(session_id, False):
                try:
                    audio_bytes = base64.b64decode(audio_b64, validate=True)
                    # Use a single audio task per session
                    current_audio_task = manager.audio_tasks.get(session_id)
                    if current_audio_task and not current_audio_task.done():
                        current_audio_task.cancel()
                    manager.audio_tasks[session_id] = asyncio.create_task(
                        handle_incoming_audio(session_id, audio_bytes, synap)
                    )
                except binascii.Error as e:
                    logger.error(f"Invalid base64 audio data: {e}")
        
        elif message_type in ("text_message", "chat"):
            await handle_chat_message(session_id, content, message, synap)
        
        elif message_type == "client_ready":
            client_user_id = message.get("user_id", session_id)
            client_audio = message.get("audio_capable", False)
            if client_audio:
                manager.audio_streams[session_id] = True
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.HANDSHAKE.value,
                content={
                    "user_id": client_user_id,
                    "audio_streaming": manager.audio_streams[session_id],
                    "sample_rate": 16000,
                    "format": "S16_LE"
                }
            ), increment_count=False)
            logger.info(f"🤝 Handshake complete for {session_id} (audio: {client_audio})")
        
        elif message_type == "thought_inject":
            thought = await generate_random_thought(content)
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.THOUGHT.value,
                content=thought
            ), increment_count=False)
        
        elif message_type == "tool_execute":
            tool_name = message.get("tool", content)
            params = message.get("params", {})
            result = await execute_tool(tool_name, params)
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.TOOL_EXECUTION.value,
                content=result
            ), increment_count=False)
        
        elif message_type == "memory_search":
            results = []
            if hasattr(synap, 'memory') and hasattr(synap.memory, 'search'):
                results = synap.memory.search(content, limit=5) or []
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.MEMORY_RECALL.value,
                content={"results": results, "count": len(results)}
            ), increment_count=False)
        
        elif message_type == "ping":
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.STATUS.value,
                content={"type": "pong", "timestamp": time.time()}
            ), increment_count=False)
        
        elif message_type == "get_status":
            status = await get_system_status()
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.SYSTEM_STATE.value,
                content=status
            ), increment_count=False)
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
            await manager.send_message(session_id, WebSocketMessage(
                type=MessageType.ERROR.value,
                content=f"Unknown message type: {message_type}"
            ), increment_count=False)
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        await manager.send_message(session_id, WebSocketMessage(
            type=MessageType.ERROR.value,
            content=f"Invalid JSON: {str(e)}"
        ), increment_count=False)