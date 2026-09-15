#!/usr/bin/env python3
"""
CODE DATABASE — Redis (fast lookup) + Chroma (semantic search) + JSON (fallback)
Indexes your codebase so Deepseek 14B can reference it.
"""

import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger("CodeDB")

CODE_DB_PATH = Path("/home/aaron/Synap-Forge/mcp/code_db")
CHROMA_PATH  = Path("/home/aaron/Synap-Forge/mcp/chroma_db")

# Optional backends — degrade gracefully if not installed
_redis_client  = None
_chroma_client = None
_collection    = None


def _init_redis():
    global _redis_client
    try:
        import redis
        r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
        r.ping()
        _redis_client = r
        logger.info("CodeDB: Redis connected")
    except Exception as e:
        logger.warning(f"CodeDB: Redis unavailable ({e}), using JSON fallback")


def _init_chroma():
    global _chroma_client, _collection
    try:
        import chromadb
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        try:
            _collection = _chroma_client.get_collection("code_db")
        except Exception:
            _collection = _chroma_client.create_collection("code_db")
        logger.info(f"CodeDB: Chroma connected ({_collection.count()} entries)")
    except Exception as e:
        logger.warning(f"CodeDB: Chroma unavailable ({e}), semantic search disabled")


def _init():
    CODE_DB_PATH.mkdir(parents=True, exist_ok=True)
    _init_redis()
    _init_chroma()


def _code_id(name: str, code: str) -> str:
    return hashlib.md5(f"{name}:{code[:50]}".encode()).hexdigest()[:16]


def add_code(name: str, code: str, language: str = "python",
             description: str = "") -> str:
    """Add a code snippet to the database. Returns the code_id."""
    cid = _code_id(name, code)
    now = datetime.now().isoformat()

    data = {
        "id": cid,
        "name": name,
        "code": code,
        "language": language,
        "description": description,
        "timestamp": now
    }

    # JSON (always)
    (CODE_DB_PATH / f"{cid}.json").write_text(json.dumps(data, indent=2))

    # Redis
    if _redis_client:
        try:
            _redis_client.hset(f"code:{cid}", mapping={
                k: v for k, v in data.items() if isinstance(v, str)
            })
            _redis_client.sadd(f"code_lang:{language}", cid)
            _redis_client.sadd("code_all", cid)
        except Exception as e:
            logger.warning(f"CodeDB Redis write error: {e}")

    # Chroma
    if _collection:
        try:
            doc = f"{name}: {description}\n{code[:500]}"
            _collection.upsert(
                documents=[doc],
                metadatas=[{"name": name, "language": language, "cid": cid}],
                ids=[cid]
            )
        except Exception as e:
            logger.warning(f"CodeDB Chroma write error: {e}")

    return cid


def search_code(query: str, language: Optional[str] = None,
                limit: int = 5) -> List[Dict]:
    """Search code database. Returns list of matching entries."""
    results = []

    # Chroma semantic search (best quality)
    if _collection:
        try:
            n = min(limit, _collection.count()) if _collection.count() > 0 else 0
            if n > 0:
                cr = _collection.query(query_texts=[query], n_results=n)
                for cid in (cr["ids"][0] if cr["ids"] else []):
                    if language:
                        meta = cr["metadatas"][0][cr["ids"][0].index(cid)] if cid in cr["ids"][0] else {}
                        if meta.get("language") != language:
                            continue
                    entry = _get_by_id(cid)
                    if entry:
                        results.append(entry)
        except Exception as e:
            logger.warning(f"CodeDB Chroma search error: {e}")

    # Redis keyword fallback
    if not results and _redis_client:
        try:
            all_ids = _redis_client.smembers("code_all")
            ql = query.lower()
            for cid in list(all_ids)[:50]:
                d = _redis_client.hgetall(f"code:{cid}")
                if not d:
                    continue
                if language and d.get("language") != language:
                    continue
                if ql in d.get("name", "").lower() or ql in d.get("code", "").lower():
                    results.append(d)
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.warning(f"CodeDB Redis search error: {e}")

    # JSON keyword fallback
    if not results:
        ql = query.lower()
        for jf in sorted(CODE_DB_PATH.glob("*.json"),
                         key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                d = json.loads(jf.read_text())
                if language and d.get("language") != language:
                    continue
                if ql in d.get("name", "").lower() or ql in d.get("code", "").lower():
                    results.append(d)
                    if len(results) >= limit:
                        break
            except Exception:
                pass

    return results[:limit]


def get_code_by_name(name: str) -> Optional[Dict]:
    """Get a specific code entry by name."""
    name_l = name.lower()

    if _redis_client:
        try:
            for cid in _redis_client.smembers("code_all"):
                d = _redis_client.hgetall(f"code:{cid}")
                if d.get("name", "").lower() == name_l:
                    return d
        except Exception:
            pass

    for jf in CODE_DB_PATH.glob("*.json"):
        try:
            d = json.loads(jf.read_text())
            if d.get("name", "").lower() == name_l:
                return d
        except Exception:
            pass

    return None


def _get_by_id(cid: str) -> Optional[Dict]:
    if _redis_client:
        try:
            d = _redis_client.hgetall(f"code:{cid}")
            if d:
                return d
        except Exception:
            pass
    jf = CODE_DB_PATH / f"{cid}.json"
    if jf.exists():
        try:
            return json.loads(jf.read_text())
        except Exception:
            pass
    return None


def import_directory(directory: str, language: str = "python",
                     skip_dirs: Optional[List[str]] = None) -> int:
    """Bulk-import all files of a given extension from a directory tree."""
    skip_dirs = skip_dirs or ["__pycache__", "chroma_db", "code_db", ".git", "build"]
    ext_map = {
        "python": "*.py", "kotlin": "*.kt", "java": "*.java",
        "javascript": "*.js", "typescript": "*.ts", "xml": "*.xml"
    }
    pattern = ext_map.get(language, f"*.{language}")
    base = Path(directory)
    count = 0

    for f in base.rglob(pattern):
        if any(s in f.parts for s in skip_dirs):
            continue
        try:
            code = f.read_text(errors="replace")
            if len(code) < 30:
                continue
            add_code(
                name=f.name,
                code=code,
                language=language,
                description=str(f.relative_to(base))
            )
            count += 1
        except Exception as e:
            logger.warning(f"CodeDB import error {f}: {e}")

    return count


def stats() -> Dict:
    result = {"json_files": len(list(CODE_DB_PATH.glob("*.json")))}
    if _redis_client:
        try:
            result["redis_entries"] = _redis_client.scard("code_all")
        except Exception:
            result["redis_entries"] = 0
    if _collection:
        try:
            result["chroma_entries"] = _collection.count()
        except Exception:
            result["chroma_entries"] = 0
    return result


# Initialize on import
_init()
