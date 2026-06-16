#!/usr/bin/env python3
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
import requests
from urllib.parse import quote  # Import để sửa triệt để lỗi mã hóa ký tự URL

PROM_URL = "http://localhost:9090"

# Sử dụng metric thô cơ bản nhất của bản thân Prometheus làm đích kiểm tra trực tiếp
DEFAULT_QUERIES = [
    "prometheus_http_requests_total",
    "go_memstats_alloc_bytes"
]

def query_instant(q: str) -> float | None:
    try:
        # Triệt để hóa việc mã hóa các ký tự đặc biệt như (, ), {, }, =
        encoded_query = quote(q)
        url = f"{PROM_URL}/api/v1/query?query={encoded_query}"
        
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json().get("data", {}).get("result", [])
        
        if not data:
            return None
            
        vals = [float(v[1]) for v in (d["value"] for d in data) if v[1] not in ("NaN", "+Inf")]
        return statistics.mean(vals) if vals else None
    except Exception as e:
        print(f"[DEBUG ERROR] Query failure for '{q}': {e}")
        return None

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=300, help="seconds")
    ap.add_argument("--interval", type=int, default=10, help="seconds between samples")
    ap.add_argument("--out", default="baseline.json")
    ap.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES)
    args = ap.parse_args()

    samples: dict[str, list[float]] = {q: [] for q in args.queries}
    start = time.time()
    print(f"Capturing baseline for {args.duration}s, sampling every {args.interval}s...")
    
    while time.time() - start < args.duration:
        for q in args.queries:
            v = query_instant(q)
            if v is not None:
                samples[q].append(v)
            else:
                print(f"[WARN] Metric '{q}' returned no data at this point.")
        time.sleep(args.interval)

    out = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": args.duration,
        "metrics": {},
    }
    for q, vals in samples.items():
        if vals:
            vals_sorted = sorted(vals)
            p99_idx = max(0, int(len(vals_sorted) * 0.99) - 1)
            out["metrics"][q] = {
                "mean": statistics.mean(vals),
                "p99": vals_sorted[p99_idx],
                "samples": len(vals),
            }
            
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {args.out} — {len(out['metrics'])} metric series captured.")

if __name__ == "__main__":
    main()