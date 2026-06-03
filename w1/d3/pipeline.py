import csv
import time
import threading
import queue
from collections import deque
import pandas as pd
import numpy as np

FILE_PATH = 'machine_temperature_system_failure.csv'
OUTPUT_PATH = 'features.parquet'
WINDOW_SIZE = 12 

def producer(q, file_path):
    """
    Mô phỏng nguồn phát dữ liệu (vd: Cảm biến đẩy data vào Kafka)
    """
    print("[Producer] Bắt đầu đọc dữ liệu từ CSV...")
    try:
        with open(file_path, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                event = {
                    'timestamp': row['timestamp'],
                    'value': float(row['value'])
                }
                q.put(event) 
        
        print("[Producer] Hoàn thành việc gửi dữ liệu.")
    except FileNotFoundError:
        print(f"[Lỗi] Không tìm thấy file {file_path}. Vui lòng kiểm tra lại đường dẫn.")
    finally:
        q.put(None) 

def consumer(q, output_path):
    """
    Mô phỏng bộ xử lý luồng (vd: Apache Flink)
    """
    print("[Consumer] Bắt đầu nhận và tính toán features...")
    window = deque(maxlen=WINDOW_SIZE)
    features_list = []
    last_value = None

    while True:
        event = q.get()
        if event is None: 
            break

        current_val = event['value']
        window.append(current_val)

        rolling_mean = np.mean(window) if len(window) > 0 else current_val
 
        rolling_std = np.std(window) if len(window) > 1 else 0.0

        rate_of_change = current_val - last_value if last_value is not None else 0.0
        last_value = current_val

        features_list.append({
            'timestamp': event['timestamp'],
            'original_value': current_val,
            'rolling_mean': rolling_mean,
            'rolling_std': rolling_std,
            'rate_of_change': rate_of_change
        })
        q.task_done()

    print(f"[Consumer] Đang xuất dữ liệu ra {output_path}...")
    df = pd.DataFrame(features_list)
    df['timestamp'] = pd.to_datetime(df['timestamp']) 
    df.to_parquet(output_path, engine='pyarrow', index=False)
    print("[Consumer] Hoàn tất! Đã tạo file features.parquet.")

if __name__ == "__main__":
    data_queue = queue.Queue()

    prod_thread = threading.Thread(target=producer, args=(data_queue, FILE_PATH))
    cons_thread = threading.Thread(target=consumer, args=(data_queue, OUTPUT_PATH))

    prod_thread.start()
    cons_thread.start()

    prod_thread.join()
    cons_thread.join()
    print("--- Pipeline chạy thành công ---")