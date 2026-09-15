"""
Serialization boundary - ensures all cross‑layer data is safe and replayable.
"""

from typing import Union, Tuple, Any, Dict, List
from dataclasses import dataclass, asdict, is_dataclass
from enum import Enum
import datetime
from types import MappingProxyType


SerializablePrimitive = Union[str, int, float, bool, None]
SerializableValue = Union[
    SerializablePrimitive,
    Tuple["SerializableValue", ...],
    List["SerializableValue"],
    Dict[str, "SerializableValue"],
]


@dataclass(frozen=True)
class SerializedState:
    data: Dict[str, SerializableValue]
    version: str
    timestamp: float


def sanitize(value: Any, depth: int = 0, max_depth: int = 50) -> SerializableValue:
    """Recursively convert any object to a safe, serializable form."""
    if depth > max_depth:
        raise RecursionError(f"Serialization depth exceeded at {max_depth}")
    
    # Primitives
    if isinstance(value, (str, int, float, bool)):
        return value
    if value is None:
        return None
    
    # Enums
    if isinstance(value, Enum):
        return value.value
    
    # Dataclasses
    if is_dataclass(value) and not isinstance(value, type):
        return {k: sanitize(v, depth + 1, max_depth) for k, v in asdict(value).items()}
    
    # Collections
    if isinstance(value, tuple):
        return tuple(sanitize(v, depth + 1, max_depth) for v in value)
    if isinstance(value, list):
        return [sanitize(v, depth + 1, max_depth) for v in value]
    if isinstance(value, dict):
        return {str(k): sanitize(v, depth + 1, max_depth) for k, v in value.items()}
    
    # Timestamps
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, MappingProxyType):
        return {str(k): sanitize(v, depth + 1, max_depth) for k, v in value.items()}
    
    # REJECT UNSAFE TYPES
    unsafe_type_names = [
        'torch', 'tensor', 'cuda', 'cudnn', 'device',
        'generator', 'socket', '_io', 'async',
        'function', 'method', 'module', '_thread',
        'queue', 'multiprocessing', 'pickle', 'lock'
    ]
    
    type_name = type(value).__name__.lower()
    module_name = type(value).__module__.lower()
    
    for unsafe in unsafe_type_names:
        if unsafe in type_name or unsafe in module_name:
            raise TypeError(
                f"Boundary Breach: Cannot serialize runtime/hardware dependent type: {type(value)}. "
                f"Convert to primitive metrics first."
            )
    
    # Fallback: try string conversion
    try:
        return str(value)
    except Exception:
        raise TypeError(f"Unresolvable serialization block for type: {type(value)}")