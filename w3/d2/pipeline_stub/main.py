from fastapi import FastAPI, Query
from pydantic import BaseModel
import time

app = FastAPI()

class RCADataset(BaseModel):
    window_start: int
    window_end: int

@app.get("/alerts")
def get_alerts(since: int = Query(0)):
    # Trả về alert giả lập tương thích thời gian thực
    return [
        {
            "fire_ts": int(time.time()) - 10,
            "metric": "latency",
            "service": "payment-svc"
        }
    ]

@app.post("/rca")
def post_rca(data: RCADataset):
    # Trả về Root Cause động giả lập cấu trúc chuẩn của bài Lab
    return {
        "root_service": "payment-svc", 
        "confidence": 0.92,
        "evidence": "Egress network latency anomaly detected"
    }