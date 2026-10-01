#!/usr/bin/env bash
# run.sh — Launch SwasthiQ Clinic Front Desk Agent (Backend + Frontend)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo " Starting SwasthiQ Front Desk Agent (Sunrise Clinic)"
echo "=========================================================="

# 1. Check Python dependencies
echo ">>> Checking backend dependencies..."
python3 -m pip install -q -r backend/requirements.txt

# 2. Check Frontend build / node_modules
if [ ! -d "frontend/node_modules" ]; then
  echo ">>> Installing frontend packages..."
  (cd frontend && npm install)
fi

# 3. Trap for clean exit
cleanup() {
  echo ""
  echo ">>> Shutting down servers..."
  kill $(jobs -p) 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 4. Start FastAPI Backend
echo ">>> Starting FastAPI backend on http://localhost:8000..."
(cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
BACKEND_PID=$!

# Wait 2 seconds for backend to initialize
sleep 2

# 5. Start Vite Frontend
echo ">>> Starting Vite frontend on http://localhost:5173..."
(cd frontend && npm run dev -- --host 0.0.0.0 --port 5173) &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo " SwasthiQ Front Desk Agent is running!"
echo "   - Dashboard UI:  http://localhost:5173"
echo "   - API Endpoint:  http://localhost:8000/agent/run"
echo "   - API Docs:      http://localhost:8000/docs"
echo " Press Ctrl+C to terminate both servers."
echo "=========================================================="

wait
