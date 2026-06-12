from datetime import datetime
from drain3.template_miner import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

def parse_iso_timestamp(ts_str):
    if ts_str.endswith('Z'):
        ts_str = ts_str[:-1] + '+00:00'
    return datetime.fromisoformat(ts_str)

def extract_log_signatures_with_drain(live_logs):
    config = TemplateMinerConfig()
    config.profiling_enabled = False 
    miner = TemplateMiner(config=config)
    signatures = set()
    
    for log in live_logs:
        level = log.get("level", "INFO").upper()
        if level in ["ERROR", "CRITICAL"]:
            msg = log.get("msg", "")
            miner.add_log_message(msg)
            
    for cluster in miner.drain.clusters:
        drain_template = cluster.get_template()
        signatures.add(drain_template)
        
    return signatures

def calculate_trace_deviations(live_traces, detected_at_str):
    detected_at = parse_iso_timestamp(detected_at_str)
    trace_groups = {}
    
    for trace in live_traces:
        edge = (trace.get("from"), trace.get("to"))
        if not edge[0] or not edge[1]:
            continue
        if edge not in trace_groups:
            trace_groups[edge] = []
        trace_groups[edge].append(trace)
        
    trace_signatures = {}
    
    for edge, traces in trace_groups.items():
        baseline_p99s = []
        incident_p99s = []
        incident_errors = 0
        incident_counts = 0
        
        for t in traces:
            ts = parse_iso_timestamp(t.get("ts"))
            p99 = t.get("p99_ms", 0.0)
            
            if ts < detected_at:
                baseline_p99s.append(p99)
            else:
                incident_p99s.append(p99)
                incident_errors += t.get("error_count", 0)
                incident_counts += t.get("count", 0)
                
        avg_baseline_p99 = sum(baseline_p99s) / len(baseline_p99s) if baseline_p99s else 1.0
        avg_incident_p99 = sum(incident_p99s) / len(incident_p99s) if incident_p99s else avg_baseline_p99
        
        p99_deviation_ratio = avg_incident_p99 / avg_baseline_p99 if avg_baseline_p99 > 0 else 1.0
        error_rate = incident_errors / incident_counts if incident_counts > 0 else 0.0
        
        trace_signatures[edge] = {
            "p99_deviation_ratio": round(p99_deviation_ratio, 4),
            "error_rate": round(error_rate, 4)
        }
        
    return trace_signatures

def derive_affected_services(live_incident, log_signatures, trace_signatures):
    affected_services = set()
    trigger_svc = live_incident.get("trigger_alert", {}).get("service")
    if trigger_svc:
        affected_services.add(trigger_svc)
        
    svc_error_counts = {}
    for log in live_incident.get("logs", []):
        level = log.get("level", "INFO").upper()
        if level in ["ERROR", "CRITICAL"]:
            svc = log.get("svc")
            if svc:
                svc_error_counts[svc] = svc_error_counts.get(svc, 0) + 1
                
    for svc, count in svc_error_counts.items():
        if count >= 5:
            affected_services.add(svc)
            
    for edge, metrics in trace_signatures.items():
        if metrics["error_rate"] > 0.05 or metrics["p99_deviation_ratio"] > 2.0:
            affected_services.add(edge[0]) 
            affected_services.add(edge[1]) 
            
    return list(affected_services)

def extract_live_features(live_incident):
    detected_at_str = live_incident["detected_at"]
    log_sigs = extract_log_signatures_with_drain(live_incident.get("logs", []))
    trace_sigs = calculate_trace_deviations(live_incident.get("traces", []), detected_at_str)
    affected_svcs = derive_affected_services(live_incident, log_sigs, trace_sigs)
    trigger_svc = live_incident.get("trigger_alert", {}).get("service", "unknown")
    
    return {
        "trigger_service": trigger_svc,
        "log_signatures": log_sigs,
        "trace_signatures": trace_sigs,
        "affected_services": affected_svcs
    }