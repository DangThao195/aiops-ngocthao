import os
import time
import yaml
import json
import sys
import subprocess
import requests
import threading
from datetime import datetime
from prometheus_client import start_http_server, Counter, Gauge

ACTIONS_COUNT = Counter('orchestrator_actions_total', 'Total actions executed', ['service', 'runbook', 'outcome'])
CIRCUIT_BREAKER_STATUS = Gauge('orchestrator_circuit_breaker', 'Status of circuit breaker', ['service'])
MUTEX_STATUS = Gauge('orchestrator_mutex_state', 'State of service mutex', ['service'])

class ClosedLoopOrchestrator:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.service_locks = {}
        self.failure_counters = {}
        self.action_history = []
        self.global_lock = threading.Lock()
        self.global_dry_run = False
        print(f"[{datetime.now()}] 🚀 Orchestrator đã khởi động. Môi trường chuẩn hóa Windows Host.")

    def log_event(self, event_type, service, action=None, result=None, extra=None):
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "service": service,
            "action": action,
            "result": result
        }
        if extra: log_entry.update(extra)
        print(json.dumps(log_entry))
        sys.stdout.flush()

    def poll_alertmanager(self):
        url = f"{self.config['alertmanager_url']}/api/v2/alerts"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Lỗi kết nối Alertmanager: {str(e)}")
        return []

    def validate_decision(self, alert_name, runbook_path):
        if runbook_path not in self.config.get('runbook_registry', []):
            self.log_event("DECISION_VALIDATION_FAILED", "unknown", action="escalate_no_auto_action", 
                           extra={"bad_runbook": runbook_path, "alertname": alert_name, "raw_decision": runbook_path})
            return False
        return True

    def check_blast_radius(self, service):
        current_time = time.time()
        self.action_history = [t for t in self.action_history if current_time - t < 60]
        if len(self.action_history) >= self.config['blast_radius']['max_actions_per_minute']:
            print(f"   ⚠️ [Blast Radius] Vượt quá giới hạn số hành động mỗi phút!")
            return False
        return True

    def verify_remediation(self, alert_name, service):
        query_template = self.config['prometheus_queries'].get(alert_name)
        if not query_template: return False
        
        prom_service = service
        if service == "closed-loop-orchestrator":
            prom_service = "closed-loop"
        
        query = query_template.replace("{service}", prom_service)
        prom_url = f"{self.config['prometheus_url']}/api/v1/query"
        thresholds = self.config['verify_thresholds']
        success_samples = 0
        intervals = thresholds['verify_timeout_seconds'] // thresholds['verify_poll_interval_seconds']
        
        print(f"[{datetime.now()}] 🛡️ Bắt đầu bước VERIFY thực tế cho {service}. Query: {query}")
        
        for idx in range(intervals):
            print(f"[{datetime.now()}] ⏳ Đang lấy mẫu Verify thực tế từ Prometheus lần {idx+1}/{intervals}...")
            time.sleep(thresholds['verify_poll_interval_seconds'])
            
            try:
                res = requests.get(prom_url, params={'query': query}, timeout=5).json()
                results = res.get('data', {}).get('result', [])
                if not results: 
                    print(f"   [Prometheus]: Chưa trả về metric (Empty query result).")
                    success_samples = 0
                    continue
                
                val = float(results[0]['value'][1])
                print(f"   [Prometheus]: Giá trị metric thực tế tính toán được = {val}")
                
                is_safe = False
                if alert_name == "HighLatency" and val < thresholds['latency_p99_max_ms']: 
                    is_safe = True
                elif alert_name == "HighErrorRate" and val < thresholds['error_rate_max_pct']: 
                    is_safe = True
                elif alert_name == "InstanceDown" and val == thresholds['up_required']: 
                    is_safe = True
                
                if is_safe:
                    success_samples += 1
                    print(f"   ✅ Mẫu đạt yêu cầu liên tiếp: {success_samples}/{thresholds['verify_min_samples']}")
                    if success_samples >= thresholds['verify_min_samples']: 
                        return True
                else:
                    print(f"   ❌ Mẫu VƯỢT NGƯỠNG AN TOÀN. Reset bộ đếm.")
                    success_samples = 0
            except Exception as e:
                print(f"   ❌ Lỗi kết nối hoặc xử lý dữ liệu Prometheus: {str(e)}")
                success_samples = 0
        return False

    def execute_runbook(self, cmd):
        try:
            service_name = cmd[3] if len(cmd) > 3 else "payment-svc"
            is_dry_run = "--dry-run" in cmd or self.global_dry_run
            if "orchestrator" in service_name: service_name = "payment-svc"
            container_name = f"ronki-{service_name}"
            
            if is_dry_run:
                target_cmd = f"docker ps -a --filter name={container_name} --format \"{{{{.Names}}}}\""
            else:
                target_cmd = f"docker restart {container_name}"
            
            print(f"[{datetime.now()}] 🚀 Thực thi lệnh: {target_cmd}")
            subprocess.run(target_cmd, capture_output=True, text=True, timeout=30, shell=True)
            return 0
        except Exception as e:
            return -1

    def process_alert(self, alert):
        alert_name = alert.get('labels', {}).get('alertname')
        service = alert.get('labels', {}).get('service')
        status_state = alert.get('status', {}).get('state')
        
        if status_state != 'active' or not alert_name or not service:
            return

        if service not in self.service_locks:
            self.service_locks[service] = threading.Lock()
            self.failure_counters[service] = 0

        if self.failure_counters[service] >= 3:
            self.log_event("CIRCUIT_BREAKER_HALT", service, action=self.config['runbook_map'].get(alert_name), result="HALT")
            return

        runbook = self.config['runbook_map'].get(alert_name)
        if not runbook: return

        if not self.validate_decision(alert_name, runbook):
            return

        if not self.check_blast_radius(service):
            return

        self.log_event("ALERT_DETECTED", service, action=runbook)
        self.log_event("DECIDE_RUNBOOK", service, action=runbook)
        
        acquired = self.service_locks[service].acquire(blocking=False)
        if not acquired: 
            self.log_event("SERVICE_LOCK_BUSY", service, action=runbook)
            return

        try:
            self.log_event("BLAST_RADIUS_OK", service, action=runbook)
            self.action_history.append(time.time())

            if self.execute_runbook(["bash", runbook, "--service", service, "--dry-run"]) != 0:
                self.log_event("DRY_RUN_FAIL", service, action=runbook)
                return
            self.log_event("DRY_RUN_PASS", service, action=runbook)

            self.log_event("ACTION_EXECUTED", service, action=runbook)
            exec_code = self.execute_runbook(["bash", runbook, "--service", service])
            
            if exec_code == 0:
                if self.verify_remediation(alert_name, service):
                    self.log_event("VERIFY_PASS", service, action=runbook)
                    self.log_event("ACTION_SUCCESS", service, action=runbook)
                    self.failure_counters[service] = 0
                    return
                else:
                    self.log_event("VERIFY_FAIL", service, action=runbook)
                    self.log_event("ROLLBACK_TRIGGERED", service, action=runbook)
                    rollback_runbook = self.config['rollback_map'].get(alert_name, runbook)
                    self.execute_runbook(["bash", rollback_runbook, "--service", service])
                    self.log_event("ROLLBACK_EXECUTED", service, action=runbook)
            else:
                self.log_event("ACTION_EXEC_FAILED", service, action=runbook)
            
            self.failure_counters[service] += 1
            print(f"   [Circuit Breaker]: Tăng bộ đếm lỗi liên tiếp lên: {self.failure_counters[service]}/3")
        finally:
            self.service_locks[service].release()

    def start(self):
        start_http_server(9100)
        while True:
            alerts = self.poll_alertmanager()
            active_alerts = [a for a in alerts if a.get('status', {}).get('state') == 'active']
            for alert in active_alerts:
                threading.Thread(target=self.process_alert, args=(alert,)).start()
            time.sleep(5)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    orchestrator = ClosedLoopOrchestrator(config_path=args.config)
    orchestrator.global_dry_run = args.dry_run
    orchestrator.start()