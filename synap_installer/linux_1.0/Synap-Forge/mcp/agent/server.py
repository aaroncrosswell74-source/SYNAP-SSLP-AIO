"""HTTP server with rate limiting, authentication, and user context"""

from flask import Flask, request, Response, jsonify
import logging
import os
import json
import requests
import time
from .core import run_agent
from .context import set_request_id, set_request_headers, generate_request_id
from .config import TARGET_URL, MCP_URL, AUTH_TOKEN, REQUIRE_AUTH, MAX_REQUEST_SIZE
from .ratelimit import get_rate_limiter
from .audit import log_audit_event

logger = logging.getLogger("Server")

def create_app(target_url: str, mcp_url: str) -> Flask:
    """Create and configure the Flask app"""
    app = Flask(__name__)
    
    # Limit request size
    app.config['MAX_CONTENT_LENGTH'] = MAX_REQUEST_SIZE

    @app.before_request
    def add_request_id():
        """Generate request ID for every request"""
        request_id = request.headers.get('X-Request-ID', generate_request_id())
        set_request_id(request_id)
        set_request_headers(dict(request.headers))
        request.request_id = request_id
        logger.info(f"[{request_id}] Incoming {request.method} {request.path}")

    @app.before_request
    def authenticate():
        """Authenticate requests if auth is required"""
        if not REQUIRE_AUTH:
            request.user_id = "anonymous"
            return
        
        request_id = getattr(request, 'request_id', 'unknown')
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            logger.warning(f"[{request_id}] Missing authentication")
            return {"error": "Authentication required"}, 401
        
        token = auth_header.split(' ')[1]
        if token != AUTH_TOKEN:
            logger.warning(f"[{request_id}] Invalid authentication token")
            log_audit_event(
                event_type="auth_failure",
                status="error",
                error="Invalid token"
            )
            return {"error": "Invalid authentication token"}, 401
        
        request.user_id = "authenticated_user"

    @app.before_request
    def rate_limit():
        """Apply rate limiting"""
        request_id = getattr(request, 'request_id', 'unknown')
        user_id = getattr(request, 'user_id', 'anonymous')
        
        limiter = get_rate_limiter()
        allowed, retry_after = limiter.is_allowed(user_id)
        
        if not allowed:
            logger.warning(f"[{request_id}] Rate limit exceeded for {user_id}")
            return {
                "error": {
                    "type": "rate_limit",
                    "message": "Rate limit exceeded",
                    "retry_after": retry_after
                }
            }, 429

    @app.after_request
    def log_response(response):
        """Log response status"""
        request_id = getattr(request, 'request_id', 'unknown')
        logger.info(f"[{request_id}] Response: {response.status_code}")
        return response

    @app.route("/v1/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    def proxy(path):
        request_id = getattr(request, 'request_id', 'unknown')
        logger.info(f"[{request_id}] 📥 Incoming request: {request.method} {path}")
        logger.info(f"[{request_id}] 📋 Headers: {dict(request.headers)}")

        if request.method != "POST":
            return {"error": "Only POST supported"}, 405

        try:
            payload = request.get_json(force=True)
        except Exception as e:
            logger.error(f"[{request_id}] JSON parse error: {e}")
            return {"error": "Invalid JSON"}, 400

        if "chat/completions" in path:
            # Check for streaming
            if payload.get("stream", False):
                return {
                    "error": {
                        "type": "unsupported_feature",
                        "message": "Streaming with tool execution is not implemented",
                        "param": "stream"
                    }
                }, 400
            
            try:
                # --- INTENT ROUTER: Check for tool commands before model ---
                messages = payload.get("messages", [])
                if messages:
                    user_content = messages[-1].get("content", "")
                    from .parser import extract_intent_from_text
                    from .mcp import execute_tool
                    
                    intents = extract_intent_from_text(user_content)
                    logger.info(f"[{request_id}] 🔍 Parsed user_content: {repr(user_content)}")
                    logger.info(f"[{request_id}] 🎯 Extracted intents: {intents}")
                    if intents:
                        logger.info(f"[{request_id}] 🚀 Taking TOOL path for: {intents[0]['name']}")
                        logger.info(f"[{request_id}] 🎯 Intent intercepted: {intents[0]['name']} - bypassing model")
                        
                        # Execute the tool directly
                        success, error, result = execute_tool(intents[0]["name"], intents[0]["arguments"])
                        
                        # Format response
                        if success:
                            response_text = "✅ Tool executed successfully:\n" + json.dumps(result, indent=2)
                        else:
                            response_text = "❌ Tool execution failed: " + error
                        
                        # Return as OpenAI-compatible response
                        return Response(
                            json.dumps({
                                "id": "chatcmpl-" + str(abs(hash(response_text))),
                                "object": "chat.completion",
                                "created": int(time.time()),
                                "model": "weaver",
                                "choices": [{
                                    "index": 0,
                                    "message": {
                                        "role": "assistant",
                                        "content": response_text
                                    },
                                    "finish_reason": "stop"
                                }],
                                "usage": {
                                    "prompt_tokens": 0,
                                    "completion_tokens": len(response_text.split()),
                                    "total_tokens": len(response_text.split())
                                }
                            }),
                            status=200,
                            content_type="application/json"
                        )
                # --- End intent router ---
                
                logger.info(f"[{request_id}] 📤 No intents found, forwarding to MODEL")
                
                result, status_code = run_agent(payload)
                return Response(
                    json.dumps(result),
                    status=status_code,
                    content_type="application/json"
                )
            except Exception as e:
                logger.error(f"[{request_id}] Agent error: {e}")
                return {"error": str(e)}, 500

        # Forward other requests
        try:
            resp = requests.request(
                method=request.method,
                url=f"{target_url}/{path}",
                headers={k: v for k, v in request.headers if k.lower() not in ("host", "content-length")},
                json=payload,
                timeout=60
            )
            return Response(
                resp.content,
                status=resp.status_code,
                content_type=resp.headers.get("content-type", "application/json")
            )
        except Exception as e:
            logger.error(f"[{request_id}] Proxy error: {e}")
            return {"error": str(e)}, 502

    @app.route("/health")
    def health():
        return {
            "status": "ok",
            "interceptor": "running",
            "target": target_url,
            "mcp": mcp_url,
            "max_tool_rounds": int(os.getenv("MAX_TOOL_ROUNDS", "5")),
            "tools_count": len(__import__('agent.tools').tools.TOOLS)
        }

    @app.route("/ready")
    def ready():
        """Readiness check with dependency health"""
        results = {"status": "ok", "checks": {}}
        
        # Check model
        try:
            resp = requests.get(
                f"{target_url}/models",
                timeout=5
            )
            results["checks"]["model"] = resp.status_code == 200
        except:
            results["checks"]["model"] = False
        
        # Check MCP
        try:
            resp = requests.get(
                f"{mcp_url}/health",
                timeout=5
            )
            results["checks"]["mcp"] = resp.status_code == 200
        except:
            results["checks"]["mcp"] = False
        
        if not all(results["checks"].values()):
            results["status"] = "degraded"
        
        return jsonify(results)

    @app.route("/v1/models", methods=["GET"])
    def models():
        try:
            resp = requests.get(f"{target_url}/models")
            return Response(resp.content, status=resp.status_code, content_type="application/json")
        except Exception as e:
            return {"error": str(e)}, 502

    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Not found"}, 404

    @app.errorhandler(500)
    def internal_error(e):
        return {"error": "Internal server error"}, 500

    return app

# WSGI entry point for Gunicorn
application = create_app(
    target_url=TARGET_URL,
    mcp_url=MCP_URL
)
