#!/usr/bin/env bash
set -e
echo "=== Starting Custom Stack ==="
docker compose up -d
echo "Waiting for pipeline to respond..."
timeout 120 bash -c 'until curl -sf http://localhost:8000/alerts?since=0 >/dev/null; do sleep 2; done'
echo "Stack is ready!"