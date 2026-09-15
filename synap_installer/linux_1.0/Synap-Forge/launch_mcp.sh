#!/bin/bash
# MCP Ecosystem Launcher

echo "🧠 SYNAP-FORGE MCP ECOSYSTEM"
echo "============================"
echo ""

# Check if services are running
check_port() {
    timeout 2 nc -z localhost $1 2>/dev/null && echo "✅ Port $1: running" || echo "❌ Port $1: not running"
}

# Kill existing processes
echo "🧹 Cleaning up existing MCP processes..."
pkill -f "mcp_server.py" 2>/dev/null
pkill -f "mcp_interceptor.py" 2>/dev/null
sleep 1

# Start MCP Gateway
echo "🚪 Starting MCP Gateway (port 11440)..."
python3 mcp_server.py &
MCP_PID=$!
sleep 3

# Check if it started
if ps -p $MCP_PID > /dev/null 2>&1; then
    echo "✅ MCP Gateway started (PID: $MCP_PID)"
else
    echo "❌ MCP Gateway failed to start"
fi

# Check MCP Server port
echo ""
echo "📊 Service Status:"
check_port 11440  # Gateway
check_port 11438  # MCP Server (if running)

# Test Gateway health
echo ""
echo "🧪 Testing Gateway health..."
curl -s http://localhost:11440/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  ⚠️  Gateway health check failed"

# Test tools endpoint
echo ""
echo "🔧 Testing tools endpoint..."
curl -s http://localhost:11440/api/tools 2>/dev/null | python3 -m json.tool 2>/dev/null | head -20 || echo "  ⚠️  Tools endpoint failed"

echo ""
echo "✅ MCP Ecosystem ready!"
echo ""
echo "Commands:"
echo "  - Health:    curl http://localhost:11440/health"
echo "  - Tools:     curl http://localhost:11440/api/tools"
echo "  - Chat:      curl -X POST http://localhost:11440/api/chat -H 'Content-Type: application/json' -d '{\"message\":\"test\"}'"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
wait $MCP_PID 2>/dev/null
