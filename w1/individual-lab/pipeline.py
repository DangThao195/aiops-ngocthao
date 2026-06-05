import json
import os
from datetime import datetime, timezone
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()
ALERTS_FILE = "alerts.jsonl"

ALERT_FIRED = False


def detect_anomaly_fast(metrics, logs):
    """Hàm lõi phân tích Metric và Log để phát hiện + phân loại sự cố."""
    mem_usage = metrics["memory_usage_bytes"]
    mem_limit = metrics["memory_limit_bytes"]
    mem_utilization = mem_usage / mem_limit

    latency = metrics["http_p99_latency_ms"]
    rps = metrics["http_requests_per_sec"]
    timeout_rate = metrics["upstream_timeout_rate"]
    queue_depth = metrics["queue_depth"]

    log_dump = " ".join([l["message"] for l in logs]).lower()

    if mem_utilization > 0.75 or "outofmemory" in log_dump:
        return {
            "type": "memory_leak",
            "message": f"Critical memory leak! RAM Utilization at {mem_utilization*100:.1f}%.",
        }

    if (
        timeout_rate > 15.0
        or latency > 500.0
        or "circuit breaker" in log_dump
        or "upstream timeout" in log_dump
    ):
        return {
            "type": "dependency_timeout",
            "message": f"Dependency Timeout! Rate: {timeout_rate}%, Latency: {latency}ms.",
        }

    if (
        rps > 300.0
        or queue_depth > 40
        or "overloaded" in log_dump
        or "queue depth high" in log_dump
    ):
        return {
            "type": "traffic_spike",
            "message": f"Traffic Spike! RPS: {rps}, Queue Depth: {queue_depth}.",
        }

    return None


@app.post("/ingest")
async def ingest(request: Request):
    global ALERT_FIRED

    payload = await request.json()
    metrics = payload["metrics"]
    logs = payload["logs"]
    timestamp = payload["timestamp"]

    mem_util = (
        metrics["memory_usage_bytes"] / metrics["memory_limit_bytes"]
    ) * 100

    print(
        f"[{timestamp}] INGEST - RAM: {mem_util:.1f}% | RPS: {metrics['http_requests_per_sec']:.1f} | Latency: {metrics['http_p99_latency_ms']:.1f}ms | Timeout Rate: {metrics['upstream_timeout_rate']}% | Logs: {len(logs)}"
    )

    if not ALERT_FIRED:
        anomaly = detect_anomaly_fast(metrics, logs)

        if anomaly:

            alert_payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(
                    timespec="milliseconds"
                ),
                "type": anomaly["type"],
                "severity": "critical",
                "message": anomaly["message"],
            }

            with open(ALERTS_FILE, "a") as f:
                f.write(json.dumps(alert_payload) + "\n")
    
            print(
                f"[ALERT FIRED] TYPE: {anomaly['type'].upper()}"
            )
            print(f"MESSAGE: {anomaly['message']}")


            ALERT_FIRED = True

    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)