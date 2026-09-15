"""Weaver model client"""

import requests
import logging
import copy
from typing import Dict, Any, Optional, Tuple, List

from .config import TARGET_URL

logger = logging.getLogger("ModelClient")


def call_model(
    messages: List[Dict[str, Any]],
    original_payload: Dict[str, Any],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: str = "auto"
) -> Tuple[Optional[Dict[str, Any]], int]:
    """
    Call Weaver and return response with status code.

    Returns:
        (response_dict, status_code)
    """

    payload = copy.deepcopy(original_payload)

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    payload["messages"] = messages
    payload["stream"] = False

    try:
        resp = requests.post(
            f"{TARGET_URL}/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )

        if resp.status_code == 200:
            return resp.json(), 200

        logger.error(f"Model returned {resp.status_code}: {resp.text[:200]}")
        return None, resp.status_code

    except requests.exceptions.Timeout:
        logger.error("Model request timed out")
        return None, 504

    except Exception as e:
        logger.error(f"Model call failed: {e}")
        return None, 500