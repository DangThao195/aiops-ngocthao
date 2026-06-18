# pipeline.py
import argparse
import os
import pandas as pd
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from sklearn.ensemble import IsolationForest

def train_pipeline(data_path, contamination=0.02, n_estimators=100, is_retrain=False):
    """
    Hàm huấn luyện mô hình IsolationForest dựa trên dữ liệu động được truyền vào
    và đăng ký tường minh lên Docker MLflow Registry trung tâm.
    """
    # Trỏ định danh Experiment đồng bộ toàn luồng hệ thống
    mlflow.set_experiment("Anomaly-Detection-Lifecycle")
    
    # Đọc dữ liệu động truyền từ tham số (Bypass hoàn toàn lỗi hardcode đường dẫn)
    df = pd.read_csv(data_path)
    features = ['latency_p99', 'error_rate', 'rps']
    X = df[features]
    
    model_name = "anomaly-detector"
    
    # Thiết lập cấu trúc luồng chạy (Hỗ trợ Nested Run cho quá trình retrain cửa sổ trượt)
    with mlflow.start_run(run_name="isolation_forest_train", nested=is_retrain) as run:
        model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=42
        )
        model.fit(X)
        
        # Ghi nhận các tham số huấn luyện lên MLflow Server
        mlflow.log_param("contamination", contamination)
        mlflow.log_param("n_estimators", n_estimators)
        
        # Log model lên Artifact Store vật lý trung tâm
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model"
        )
        
        # Khởi tạo client để kiểm soát và đăng ký mô hình thủ công an toàn hệ thống
        client = MlflowClient()
        try:
            client.create_registered_model(model_name)
        except Exception:
            # Bỏ qua nếu mô hình anomaly-detector đã tồn tại trong Registry
            pass
            
        # Đăng ký chính thức Artifact vừa sinh ra thành một phiên bản mô hình mới
        model_src = f"{run.info.artifact_uri}/model"
        mv = client.create_model_version(model_name, model_src, run.info.run_id)
        
        # Trả về số hiệu phiên bản dạng chuỗi và Run ID để phục vụ khâu kiểm định Holdout
        return str(mv.version), run.info.run_id

if __name__ == "__main__":
    # Hỗ trợ khởi chạy độc lập từ giao diện dòng lệnh Terminal
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="Đường dẫn tới tệp dữ liệu CSV huấn luyện")
    args = parser.parse_args()
    
    version, run_id = train_pipeline(args.data)
    print(f" Successfully trained and registered model version: {version} (Run ID: {run_id})")