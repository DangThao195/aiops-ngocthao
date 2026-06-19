# serve.py
import uvicorn
from fastapi import FastAPI, BackgroundTasks
import mlflow.pyfunc
import pandas as pd
from pydantic import BaseModel
from contextlib import asynccontextmanager

model_name = "anomaly-detector"
current_model = None
active_version = "None"

def load_production_model():
    global current_model, active_version
    # Tải mô hình thông qua alias production
    model_uri = f"models:/{model_name}@production"
    current_model = mlflow.pyfunc.load_model(model_uri)
    
    # Lấy thông tin cụ thể của version từ metadata ứng với alias
    from mlflow.tracking import MlflowClient
    client = MlflowClient()
    aliases = client.get_registered_model(model_name).aliases
    active_version = aliases.get("production", "unknown")
    print(f"Loaded model version {active_version} from alias @production")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo khi start server
    load_production_model()
    yield

app = FastAPI(lifespan=lifespan)

class PredictRequest(BaseModel):
    features: list # [[latency, error_rate, rps]]

@app.post("/predict")
def predict(payload: PredictRequest):
    df = pd.DataFrame(payload.features, columns=['latency_p99', 'error_rate', 'rps'])
    preds = current_model.predict(df)
    # Chuyển đổi định dạng output (Ví dụ: -1 thành 1 (Anomalous), 1 thành 0 (Normal))
    final_preds = [1 if p == -1 else 0 for p in preds]
    
    # Giả định điểm score là khoảng cách tới ranh giới phân tách (nếu có score_samples)
    # IsolationForest có score_samples, tuy nhiên tùy phiên bản mlflow wrapper ta trả về giá trị thô
    return {"prediction": final_preds[0], "score": 0.0, "version": active_version}

@app.get("/health/active-version")
def get_active_version():
    return {"active_version": active_version}

@app.post("/reload")
def reload_model():
    load_production_model()
    return {"status": "success", "reloaded_version": active_version}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)