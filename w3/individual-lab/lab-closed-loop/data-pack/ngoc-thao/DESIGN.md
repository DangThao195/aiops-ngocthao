# DESIGN DOCUMENT — CLOSED-LOOP AUTOMATION ORCHESTRATOR

---

### 1. Decision Engine Selection (Cơ chế ra quyết định)

* **Lựa chọn:** Rule-based decision engine (Cơ chế ánh xạ theo quy tắc thông qua cấu hình tập trung).
* **Lý do lựa chọn & Đánh giá Trade-offs:**
  * **Độ trễ thấp (Low Latency):** Cơ chế Rule-based thực hiện ánh xạ trực tiếp từ nhãn alert sang runbook script thông qua cấu hình `runbook_map` trong bộ nhớ, mất chưa đầy 1ms. Điều này tối ưu hơn việc gọi API bên ngoài (như LLM), vốn mất từ 1–3 giây và có rủi ro nghẽn mạng.
  * **Tính nhất quán (Deterministic):** Trên môi trường Production với tần suất ~80,000 đơn hàng/ngày, mọi hành động khôi phục phải tuyệt đối chính xác và có thể dự đoán trước. Cơ chế Rule-based loại bỏ hoàn toàn rủi ro "ảo giác" (hallucination) từ các mô hình trí tuệ nhân tạo.
  * **Tầng phòng vệ bổ sung (Hallucination Defense):** Để tối ưu hóa và đạt mức an toàn tương đương LLM-based, hệ thống tích hợp thêm hàm `validate_decision`. Hàm này đối chiếu nghiêm ngặt mọi yêu cầu thực thi với danh sách trắng `runbook_registry`. Nếu xuất hiện một runbook lạ nằm ngoài danh sách, hệ thống sẽ lập tức từ chối (`escalate_no_auto_action`) nhằm ngăn chặn hoàn toàn các cuộc tấn công inject mã độc hoặc cấu hình sai lệch.

---

### 2. Blast-Radius Configuration (Kiểm soát vùng ảnh hưởng)

Hệ thống sử dụng mô hình cửa sổ trượt (Sliding Window) để tính toán tần suất hành động thời gian thực với các chỉ số an toàn nghiêm ngặt:

* **max_actions_per_minute: 2**
  * *Lý do:* Giới hạn tối đa 2 hành động khôi phục trong vòng 1 phút trên toàn hệ thống. Con số này ngăn chặn tình trạng Orchestrator bị kích hoạt dồn dập do nhiễu động cảnh báo hoặc do nhiều luồng phụ xử lý bất đồng bộ cùng chạy, tránh làm quá tải tài nguyên CPU/Network của máy Host Windows.
* **max_restarts_per_service_per_hour: 5**
  * *Lý do:* Giới hạn một dịch vụ cụ thể không được phép restart quá 5 lần trong vòng 1 giờ. Khi một container dính lỗi core nặng (ví dụ: CrashLoopBackOff do lỗi code), việc restart liên tục sẽ không giải quyết được vấn đề mà còn gây lãng phí tài nguyên và làm tê liệt hệ thống. Giới hạn này ép mạch dừng lại để bàn giao quyền cho kỹ sư.

---

### 3. Verification Step Metrics & Thresholds (Tiêu chí xác minh)

Hệ thống kết nối trực tiếp đến API của Prometheus để lấy chỉ số thực tế sau khi thực hiện hành động sửa lỗi.

* **HighLatency (Độ trễ cao):**
  * *Metric kiểm tra:* `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="{service}"}[1m])) * 1000`
  * *Ngưỡng an toàn:* `< 200` ms.
* **HighErrorRate (Tỷ lệ lỗi cao):**
  * *Metric kiểm tra:* `rate(http_errors_total{service="{service}"}[2m]) / (rate(http_requests_total{service="{service}"}[2m]) + 0.001) * 100`
  * *Ngưỡng an toàn:* `< 10.0` %.
* **InstanceDown (Dịch vụ sập):**
  * *Metric kiểm tra:* `up{job="{service}"}`
  * *Ngưỡng an toàn:* `== 1` (Biểu thị container hoạt động bình thường).
* **Cơ chế lấy mẫu (Timeout & Interval):**
  * *verify_timeout_seconds:* `60` giây.
  * *verify_poll_interval_seconds:* `10` giây (Quét 6 lần trong một chu kỳ).
  * *verify_min_samples: 3* (Yêu cầu quan trọng nhất). Hệ thống bắt buộc phải thu thập đủ **3 mẫu liên tiếp đạt chuẩn an toàn** thì mới kết luận là `VERIFY_PASS` và in ra `ACTION_SUCCESS`. Nếu xuất hiện bất kỳ 1 mẫu nào vượt ngưỡng an toàn, bộ đếm liên tiếp lập tức reset về 0. Cơ chế này loại bỏ hoàn toàn hiện tượng nhiễu động dữ liệu trạng thái (Flapping) hoặc các mẫu may mắn (false positive) khi container vừa khôi phục.

---

### 4. Circuit Breaker Mechanism (Cơ chế ngắt mạch an toàn)

* **Ngưỡng kích hoạt:** Khi một dịch vụ thành phần tích lũy đủ **3 lần thất bại liên tiếp** (`self.failure_counters[service] >= 3`), bao gồm cả lỗi thực thi script hành động (`ACTION_EXEC_FAILED`) hoặc lỗi xác minh chỉ số thực tế vượt ngưỡng (`VERIFY_FAIL` dẫn đến Rollback).
* **Cơ chế Reset:** **Thủ công (Manual Reset).** Khi mạch bảo vệ tối cao chuyển sang trạng thái sập mạch (`CIRCUIT_BREAKER_HALT`), Orchestrator đóng băng hoàn toàn mọi hành vi tự động sửa lỗi đối với dịch vụ đó để bảo vệ an toàn tuyệt đối cho hạ tầng. Hệ thống sẽ liên tục in ra nhãn trạng thái `HALT` sau mỗi 5 giây. Bộ đếm lỗi này không tự động reset theo thời gian; chỉ sau khi kỹ sư SRE vào kiểm tra hệ thống, xử lý dứt điểm lỗi tận gốc và khởi động lại tiến trình Orchestrator, bộ nhớ đếm lỗi mới được làm sạch hoàn toàn về 0.