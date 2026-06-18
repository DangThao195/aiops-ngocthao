# DESIGN.md

## Ứng dụng dự án: Hệ thống phát hiện bất thường Gateway Thanh toán (Payment Gateway Anomaly Detection Engine)

**Thành phần luồng xử lý:** Tự động hóa phát hiện Drift, Tái huấn luyện mô hình theo Cửa sổ trượt (Sliding Window), Đánh giá kiểm định và Cơ chế tự động Rollback an toàn.

---

# 1. Tổng quan Kiến trúc Hệ thống

Hệ thống vận hành một vòng đời MLOps đóng và tự động hóa (*closed-loop, automated MLOps lifecycle*) nhằm chống lại sự suy giảm hiệu năng của mô hình do dịch chuyển dữ liệu (*Data Drift*) và dịch chuyển khái niệm (*Concept Drift*). Hệ thống liên tục giám sát các chỉ số vận hành (`latency_p99`, `error_rate`, `rps`) để duy trì ranh giới dự đoán bất thường một cách chính xác.

```text
+-------------------------------------------------+
|      BƯỚC 1: Vòng lặp Giám sát Liên tục         |
|  [FastAPI Engine:8000] ----> [Prometheus Core]  |
+-------------------------------------------------+
                         │
                         ▼
+-------------------------------------------------+
|         BƯỚC 2: Phát hiện Drift Lai             |
|  [Evidently AI Engine] & [Đánh giá Holdout]     |
+-------------------------------------------------+
                         │
      ┌──────────────────┴──────────────────┐
      ▼                                     ▼
(Nếu có Drift hoặc                    (Nếu không có Drift)
 hiệu năng giảm sâu)

+-------------------------------------------------+
| BƯỚC 3: Cơ chế Tái huấn luyện Cửa sổ trượt      |
| [IsolationForest] --> [Mlflow Client Registry]  |
+-------------------------------------------------+
                         │
                         ▼
+-------------------------------------------------+
| BƯỚC 4: Cổng Phê duyệt & Kiểm thử Hậu triển khai|
| [Operator Gate] --> [Vòng quét Giám sát 24 Chu kỳ]
+-------------------------------------------------+
                         │
                         ▼ (Nếu Precision < 0.65)

+-------------------------------------------------+
|      BƯỚC 5: Tự động Rollback An toàn           |
| [Hoán đổi Alias] --> [Ghi nhật ký Audit JSONL]  |
+-------------------------------------------------+
```

---

# 2. Chi tiết Đặc tả các Sub-Checkpoint

## Sub-checkpoint 1: Cấu hình Ngưỡng Drift (Drift Threshold)

* **Ngưỡng được chọn:** `0.15` (15% số lượng thuộc tính đầu vào bị gắn cờ drift thông qua gói `DataDriftPreset` của Evidently).
* **Cơ sở Toán học & Thực nghiệm:** Khi chạy thử nghiệm trên các phân đoạn không thay đổi của `baseline.csv`, hệ thống đo được mức nhiễu nền môi trường (*noise floor*) là `0.04`. Việc chọn ngưỡng `0.15` đóng vai trò như một bộ nhân an toàn **3.75×** so với nhiễu nền.
* Thực nghiệm trên tập dữ liệu stress test (`drifted.csv`) ghi nhận điểm số drift thực tế là `0.67` (2/3 thuộc tính bị dịch chuyển), đảm bảo kích hoạt retrain chính xác mà không bị báo động giả.

### Rủi ro nếu ngưỡng quá thấp (< 0.05)

* Gây ra tình trạng báo động giả (*false positive*).
* Cạn kiệt tài nguyên tính toán do các biến động traffic theo mùa vụ bình thường (mẫu lưu lượng ngày/đêm).

### Rủi ro nếu ngưỡng quá cao (> 0.50)

* Gây lọt lưới lỗi (*false negative*).
* Mô hình bị suy giảm hiệu năng âm thầm trong khi dữ liệu đã thay đổi nghiêm trọng.

---

## Sub-checkpoint 2: Phân loại cơ chế Drift phát hiện

### Loại Drift mục tiêu

* Data Drift (Dịch chuyển phân phối đầu vào `P(X)`).
* Kết hợp với các chỉ số Proxy giám sát hiệu năng thực tế (*Performance Monitoring*).

### Chiến lược Đo lường Thống kê

Áp dụng thuật toán khoảng cách toán học `Wasserstein Distance` trên các biến số liên tục có mật độ cao.

Ví dụ:

* Latency trung bình tăng từ `120ms` lên `156ms` sau chiến dịch marketing.
* Hệ thống vẫn phát hiện sự thay đổi dù chưa có sự sụt giảm độ chính xác rõ rệt.

---

## Sub-checkpoint 3: Cấu hình Kích hoạt Tái huấn luyện (Retrain Trigger)

### Loại Cổng (Gate Class)

**Semi-automatic**

* Tự động hóa tổng hợp dữ liệu cửa sổ trượt.
* Yêu cầu cổng phê duyệt thủ công từ Kỹ sư vận hành (*Operator Approval Gate*).

### Chu kỳ vận hành (Cadence)

* Kiểm tra bất đồng bộ thông qua các batch job dữ liệu.
* Bước thăng cấp mô hình bắt buộc phải có xác nhận của con người để bảo vệ SLA hệ thống thanh toán.

### Cơ chế an toàn dự phòng

* Timeout phê duyệt tối đa: **24 giờ**.
* Quá thời gian này, phiên bản staging sẽ tự động được lưu trữ (*archive*).

---

## Sub-checkpoint 4: Kiến trúc Định danh Phiên bản (Versioning & Rollback)

### Cơ chế định danh

Sử dụng số phiên bản bất biến (*immutable version*) ánh xạ động tới các nhãn Alias linh hoạt thông qua API `MlflowClient`.

### Ma trận định tuyến Alias

| Alias         | Vai trò                                     |
| ------------- | ------------------------------------------- |
| `@production` | Trỏ tới mô hình đang phục vụ production     |
| `@staging`    | Trỏ tới mô hình ứng viên đang được đánh giá |

### Thời gian Rollback

* Dưới **5 giây**.
* Thực hiện bằng cách:

  1. Hoán đổi alias trên Registry.
  2. Gọi API `POST /reload`.
  3. Giải phóng bộ nhớ đệm và tải lại mô hình.

Không cần deploy lại container.

---

## Sub-checkpoint 5: Cơ chế Phát hiện kết hợp (Combined Mode)

### Điểm yếu của Data Drift thuần túy

Data Drift không thể phát hiện trường hợp:

* `P(X)` không đổi.
* Nhưng mối quan hệ giữa đầu vào và nhãn (`P(Y|X)`) thay đổi.

Đây là hiện tượng **Concept Drift**.

Ví dụ:

* Đối tác thanh toán thay đổi kiến trúc xử lý.
* Hành vi gian lận mới xuất hiện.
* Phân phối dữ liệu đầu vào vẫn giữ nguyên.

### Chiến lược Combined Mode

Chạy song song hai bộ kiểm định:

1. Kiểm định phân phối thống kê (Evidently AI).
2. Đánh giá Precision/Recall trên tập dữ liệu có nhãn (`holdout.csv`).

### Điều kiện kích hoạt Retrain

```text
Drift Score > 0.15
HOẶC
Precision < 0.70
```

---

## Sub-checkpoint 6: Chiến lược Lựa chọn Dữ liệu Tái huấn luyện (Data Selection)

### Hạn chế nếu chỉ huấn luyện trên Drift Window

Nếu chỉ train trên dữ liệu mới (`drifted.csv`):

* Dễ bị overfit.
* Quên các mẫu hành vi cũ.
* Precision trên tập Holdout giảm tới 18%.

### Chiến lược Sliding Window

Sử dụng:

```python
pd.concat([baseline_df, drifted_df])
```

Trong đó:

| Dataset      | Số dòng |
| ------------ | ------- |
| baseline.csv | 4320    |
| drifted.csv  | 1008    |

Lợi ích:

* Duy trì bộ nhớ dữ liệu lịch sử.
* Hấp thụ mẫu bất thường mới.
* Mở rộng biên phân tách của Isolation Forest.

---

## Sub-checkpoint 7: Tự động Rollback và Nhật ký Audit

### Chu kỳ giám sát ổn định

Đánh giá liên tục qua:

```text
24 vòng quét hậu triển khai
(post_deploy_monitor)
```

Sử dụng tập dữ liệu:

```text
post_deploy_eval.csv
```

### Ngưỡng Kích hoạt Đáy

```text
Precision < 0.65
```

Ngưỡng này:

* Không bị kích hoạt nhầm bởi nhiễu nhỏ.
* Đủ nhạy để chặn các pha sụp đổ hiệu năng nghiêm trọng.

### Định dạng Nhật ký Audit

File:

```text
outputs/audit_log.jsonl
```

Ví dụ:

```json
{
  "event": "auto_rollback_v2_to_v1",
  "demoted_version": 19,
  "restored_version": 4,
  "trigger_precision": 0.5420,
  "cycle": 3
}
```

---

# 3. Ma trận Giám sát MLOps Observability

Giám sát MLOps khác với giám sát hạ tầng truyền thống vì tập trung vào:

* Dịch chuyển dữ liệu.
* Suy giảm độ chính xác mô hình.
* Chất lượng dự đoán.

| Tên Metric Giám sát      | Loại Metric | Vai trò                                               |
| ------------------------ | ----------- | ----------------------------------------------------- |
| `mlops_model_precision`  | Gauge       | Giám sát độ chính xác, phát hiện sớm suy giảm mô hình |
| `mlops_model_recall`     | Gauge       | Đo lường tỷ lệ bỏ sót bất thường                      |
| `retrain_triggered`      | Counter     | Đếm số lần hệ thống kích hoạt retrain                 |
| `auto_rollback_v2_to_v1` | Counter     | Cảnh báo đỏ trên Grafana khi rollback xảy ra          |

---

# 4. Tổng kết Đánh đổi Kiến trúc (Trade-offs)

| Quyết định Thiết kế      | Lợi ích Đạt được                                | Đánh đổi / Chi phí                       |
| ------------------------ | ----------------------------------------------- | ---------------------------------------- |
| Manual Approval Gate     | An toàn vận hành tối đa, kiểm soát SLA chặt chẽ | Tăng độ trễ do phụ thuộc con người       |
| Gộp dữ liệu Cửa sổ trượt | Chống quên kiến thức cũ, bao phủ dữ liệu mới    | Tăng RAM và dung lượng lưu trữ           |
| Isolation Forest         | Huấn luyện rất nhanh (<1s), triển khai đơn giản | Không xử lý tốt temporal patterns        |
| Lưu trữ Artifact Local   | Triển khai nhanh, không phụ thuộc S3/MinIO      | Không mở rộng đa nút, rủi ro mất dữ liệu |

---

# Kết luận

Kiến trúc được thiết kế theo mô hình **Closed-loop MLOps Lifecycle**, kết hợp:

* Drift Detection bằng Evidently AI.
* Retraining theo Sliding Window.
* Quản lý Model Registry bằng MLflow.
* Operator Approval Gate.
* Post-deployment Validation.
* Automatic Rollback.

Thiết kế này ưu tiên **an toàn vận hành**, **khả năng phục hồi nhanh** và **duy trì chất lượng mô hình dài hạn** trong môi trường Gateway Thanh toán có lưu lượng giao dịch biến động liên tục.
