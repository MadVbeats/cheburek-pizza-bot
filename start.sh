#!/bin/bash
set -e
PORT=${PORT:-8000}
echo "Starting Mini App on port $PORT and Telegram bot..."
python bot.py &
BOT_PID=$!
uvicorn server:app --host 0.0.0.0 --port $PORT --proxy-headers &
WEB_PID=$!
wait -n
kill $BOT_PID $WEB_PID 2>/dev/null || true
