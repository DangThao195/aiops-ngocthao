import pandas as pd
import math

tiers = {
    "Small": {"services": 10, "logs_gb_day": 50, "metrics_eps": 100_000},
    "Medium": {"services": 100, "logs_gb_day": 500, "metrics_eps": 1_000_000},
    "Large": {"services": 1000, "logs_gb_day": 5_000, "metrics_eps": 10_000_000}
}

def calculate_cost(name, data):
    svc = data["services"]
    logs = data["logs_gb_day"]
    metrics = data["metrics_eps"]

    sh_storage = (logs / 500) * 4500
    sh_compute = (metrics / 1_000_000) * 5700
    sh_infra_total = sh_storage + sh_compute

    sre_count = max(1, math.ceil(svc / 50))
    sh_people_total = sre_count * 5000
    
    sh_total = sh_infra_total + sh_people_total

    dd_infra_host = svc * 31
    dd_logs = (logs * 30) * 2.5       
    dd_metrics = (metrics / 100_000) * 1500 
    
    dd_total = dd_infra_host + dd_logs + dd_metrics

    return {
        "Scale Tier": name,
        "Services": svc,
        "Logs (GB/day)": logs,
        "Metrics (Events/sec)": f"{metrics:,}",
        "SH Infra ($)": f"${sh_infra_total:,.0f}",
        "SH People (SRE)": f"${sh_people_total:,.0f} ({sre_count})",
        "Self-host TOTAL": f"${sh_total:,.0f}",
        "Datadog TOTAL": f"${dd_total:,.0f}",
        "Tiết kiệm hơn?": "Self-host" if sh_total < dd_total else "Datadog"
    }

results = []
for tier_name, tier_data in tiers.items():
    results.append(calculate_cost(tier_name, tier_data))

df = pd.DataFrame(results)

print("\n=== BẢNG ƯỚC TÍNH CHI PHÍ AIOPS (HÀNG THÁNG) ===")

print(df.to_markdown(index=False))
print("================================================\n")