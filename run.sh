#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "========================================================"
echo "          Starting LifePilot AI Operations Center       "
echo "========================================================"

# Check virtualenv
if [ -d "myvenv2" ]; then
    PYTHON="./myvenv2/bin/python"
else
    PYTHON="python3"
fi

# Kill any existing processes on 8000 and 9000
kill $(lsof -t -i:8000) 2>/dev/null || true
kill $(lsof -t -i:9000) 2>/dev/null || true
killall cloudflared 2>/dev/null || true

# 1. Start Demo Portals on Port 9000
echo "[1/3] Starting Demo Portals on http://localhost:9000..."
$PYTHON -m uvicorn demo_portal.app:app --port 9000 > /tmp/demo_portal.log 2>&1 &
PORTAL_PID=$!

# 2. Start Cloudflare Tunnel for TinyFish cloud browser
echo "[2/3] Exposing Port 9000 via Cloudflare Tunnel for TinyFish..."
cloudflared tunnel --url http://localhost:9000 > /tmp/cloudflared.log 2>&1 &
TUNNEL_PID=$!

sleep 4
TUNNEL_URL=$(grep -o 'https://[-a-z0-9.]*trycloudflare.com' /tmp/cloudflared.log | head -n 1)

if [ -n "$TUNNEL_URL" ]; then
    echo "      Public Tunnel Live: $TUNNEL_URL"
    # Update SQLite tasks target_url with current tunnel
    sqlite3 autopilot.db "UPDATE tasks SET target_url = '$TUNNEL_URL' WHERE id = 1;" 2>/dev/null || true
    sqlite3 autopilot.db "UPDATE tasks SET target_url = '$TUNNEL_URL/passport' WHERE id = 2;" 2>/dev/null || true
    sqlite3 autopilot.db "UPDATE tasks SET target_url = '$TUNNEL_URL/scholarship' WHERE id = 5;" 2>/dev/null || true
else
    echo "      Tunnel starting in background (see /tmp/cloudflared.log)"
fi

# Function to clean up background processes on exit
cleanup() {
    echo ""
    echo "Shutting down background services..."
    kill $PORTAL_PID 2>/dev/null || true
    kill $TUNNEL_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 3. Start Main FastAPI App on Port 8000
echo "[3/3] Starting Main App on http://localhost:8000..."
echo "========================================================"
echo " LifePilot Dashboard: http://localhost:8000"
echo " Press Ctrl+C at any time to stop all services"
echo "========================================================"
$PYTHON -m uvicorn app.main:app --port 8000 --reload
