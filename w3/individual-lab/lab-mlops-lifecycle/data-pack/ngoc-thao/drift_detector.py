# drift_detector.py
import argparse
import os
import pandas as pd
import mlflow
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset
from sklearn.metrics import precision_score, recall_score
# Tích hợp module đo lường nâng cao
from metrics_util import push_drift_score

def detect_drift(reference_path, current_path, threshold=0.15, check_mode="data", model_uri=None, labeled_current_path=None):
    ref_df = pd.read_csv(reference_path)
    cur_df = pd.read_csv(current_path)
    features = ['latency_p99', 'error_rate', 'rps']
    
    # 1. Tính toán Data Drift
    drift_report = Report(metrics=[DataDriftPreset()])
    drift_report.run(reference_data=ref_df[features], current_data=cur_df[features])
    
    os.makedirs("outputs/drift_reports", exist_ok=True)
    drift_report.save_html("outputs/drift_reports/report.html")
    
    result_dict = drift_report.as_dict()
    try:
        drift_share = result_dict["metrics"][0]["result"]["share_of_drifted_features"]
    except KeyError:
        metrics_data = result_dict["metrics"][0]["result"]
        drift_share = metrics_data.get("number_of_drifted_features", 0) / metrics_data.get("number_of_features", 1)
    
    print(f"--- Drift Check Mode: {check_mode} ---")
    print(f"Drift score (share of drifted features): {drift_share:.4f}")
    
    perf_precision = None
    perf_recall = None
    
    # 2. Tính toán Performance Drift (Concept Drift)
    if check_mode in ["combined", "performance"] and model_uri and labeled_current_path:
        labeled_df = pd.read_csv(labeled_current_path)
        if 'anomaly_label' in labeled_df.columns:
            model = mlflow.pyfunc.load_model(model_uri)
            preds = model.predict(labeled_df[features])
            binary_preds = [1 if p == -1 else 0 for p in preds]
            y_true = labeled_df['anomaly_label']
            
            perf_precision = float(precision_score(y_true, binary_preds, zero_division=0))
            perf_recall = float(recall_score(y_true, binary_preds, zero_division=0))
            print(f"Perf precision: {perf_precision:.4f}")
            print(f"Perf recall: {perf_recall:.4f}")
            
    if mlflow.active_run():
        mlflow.log_metric("drift_score", drift_share)
        if perf_precision is not None:
            mlflow.log_metric("perf_precision", perf_precision)
            
    # BONUS ĐỒ THỊ: Đẩy chỉ số sang Prometheus Pushgateway
    push_drift_score(drift_share, threshold)
            
    is_drift_triggered = (drift_share > threshold) or (perf_precision is not None and perf_precision < 0.80)
    return drift_share, is_drift_triggered, perf_precision

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=str, required=True)
    parser.add_argument("--current", type=str, required=True)
    parser.add_argument("--threshold", type=float, default=0.15)
    parser.add_argument("--check-mode", type=str, default="data")
    parser.add_argument("--model-uri", type=str, default=None)
    parser.add_argument("--labeled-current", type=str, default=None)
    args = parser.parse_args()
    detect_drift(args.reference, args.current, args.threshold, args.check_mode, args.model_uri, args.labeled_current)