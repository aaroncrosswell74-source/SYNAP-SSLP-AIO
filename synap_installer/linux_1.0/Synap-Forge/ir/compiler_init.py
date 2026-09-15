import logging
from typing import Optional

from .compiler import Compiler

logger = logging.getLogger(__name__)

_compiler: Optional[Compiler] = None
_identity_engine = None


def init_compiler(identity_engine) -> Compiler:
    global _compiler, _identity_engine
    
    if _compiler is not None:
        logger.warning("⚠️ Compiler already initialized.")
        return _compiler
    
    _identity_engine = identity_engine
    _compiler = Compiler(identity_engine)
    
    logger.info(f"✅ Compiler initialized with assistant: {identity_engine.identity.assistant_name}")
    return _compiler


def get_compiler() -> Compiler:
    if _compiler is None:
        raise RuntimeError("Compiler not initialized. Call init_compiler() first.")
    return _compiler


def get_identity_engine():
    if _identity_engine is None:
        raise RuntimeError("Compiler not initialized. Call init_compiler() first.")
    return _identity_engine


def reset_compiler():
    global _compiler, _identity_engine
    _compiler = None
    _identity_engine = None
