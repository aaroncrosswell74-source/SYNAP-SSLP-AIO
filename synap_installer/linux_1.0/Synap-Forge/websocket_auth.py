# websocket_auth.py
"""
WebSocket authentication handling
"""

import jwt
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class WebSocketAuthenticator:
    """Authenticate WebSocket connections"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    async def authenticate(self, websocket, query_params: dict) -> Optional[dict]:
        """Authenticate WebSocket connection"""
        # Check for token in query params
        token = query_params.get("token")
        if not token:
            # Try to get from protocol
            token = websocket.headers.get("Authorization", "").replace("Bearer ", "")
        
        if not token:
            logger.warning("WebSocket connection without token")
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                logger.warning("WebSocket token expired")
                return None
            
            # Check for required scopes
            if "rl_control" not in payload.get("scopes", []):
                logger.warning(f"WebSocket missing rl_control scope: {payload.get('scopes', [])}")
                return None
            
            logger.info(f"WebSocket authenticated: {payload.get('sub')}")
            return {
                "user_id": payload.get("sub"),
                "scopes": payload.get("scopes", [])
            }
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid WebSocket token: {e}")
            return None
        except Exception as e:
            logger.error(f"WebSocket auth error: {e}")
            return None

# Use in websocket handler
@app.websocket("/api/rl/ws")
async def rl_websocket(websocket: WebSocket):
    """Authenticated WebSocket endpoint"""
    # Authenticate
    auth = WebSocketAuthenticator(os.getenv("JWT_SECRET"))
    user = await auth.authenticate(websocket, dict(websocket.query_params))
    
    if not user:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    # Accept connection
    await websocket.accept()
    # ... rest of WebSocket handler