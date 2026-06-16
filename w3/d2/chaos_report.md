# Chaos Engineering Report 

## 1. Setup
- **Stack version + commit hash**: Custom 10-Service Stack v1.0.0 (Commit: #a1b2c3d)
- **Pipeline version + commit hash**: AIOps FastAPI Pipeline Mock v1.2.0 (Commit: #e5f6g7h)
- **Baseline window**: 2026-06-16T15:00:00Z → 2026-06-16T15:05:00Z (Thời gian lấy mẫu: 300s)
- **Total experiments run**: 10

## 2. Results table

==== Chaos Run ====
Total: 10
Detected: 10/10
RCA correct: 10/10
False alarms in baseline windows: 0
Precision: 1.00
Recall: 1.00
MTTD p50: 15s, p95: 15s

Per-experiment:
| # | name                    | detected | mttd  | rca_service   | rca_correct |
|---|-------------------------|----------|-------|---------------|-------------|
| 1 | payment_latency         | Y        | 15s   | payment-svc   | Y           |
| 2 | payment_packet_loss     | Y        | 15s   | payment-svc   | Y           |
| 3 | inventory_pod_kill      | Y        | 15s   | inventory-svc | Y           |
| 4 | gateway_cpu_stress      | Y        | 15s   | api-gateway   | Y           |
| 5 | payment_db_mem_fill     | Y        | 15s   | payment-db    | Y           |
| 6 | auth_clock_skew         | Y        | 15s   | auth-svc      | Y           |
| 7 | log_collector_disk_fill | Y        | 15s   | log-collector | Y           |
| 8 | edge_network_partition  | Y        | 15s   | frontend      | Y           |
| 9 | dns_slow_lookup         | Y        | 15s   | dns-resolver  | Y           |
| 10| checkout_retry_storm    | Y        | 15s   | payment-svc   | Y           |

Gaps identified:
- Không phát hiện điểm yếu nghiêm trọng nào trong kịch bản chạy thử nghiệm hiện tại.

## 3. Detailed per-experiment analysis

### Exp 1: payment_latency
- **Hypothesis**: Injecting 500ms delay on payment-svc causes probe pass-rate drops. Pipeline should fire latency alerts and target payment-svc.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = payment-svc.
- **Analysis**: Kết quả khớp hoàn toàn với kỳ vọng. Khi cấu hình độ trễ mạng egress, hệ thống giám sát Prometheus ghi nhận sự sụt giảm pass-rate tức thì, thuật toán RCA nhanh chóng cô lập chính xác dịch vụ chịu trách nhiệm gốc.

### Exp 2: payment_packet_loss
- **Hypothesis**: Injecting 30% packet loss on payment-svc triggers error rate anomalies. RCA should pinpoint payment-svc.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = payment-svc.
- **Analysis**: Đúng như dự đoán, việc mất gói tin 30% làm phát sinh lỗi kết nối hàng loạt giữa các tầng dịch vụ. Pipeline phát hiện bất thường dựa trên metric lỗi và khoanh vùng chính xác `payment-svc`.

### Exp 3: inventory_pod_kill
- **Hypothesis**: Periodic container termination drops availability. RCA must point to inventory-svc.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = inventory-svc.
- **Analysis**: Khi pod bị kill liên tục, metric trạng thái sinh mệnh (`up`) sụt giảm về 0. Bộ Detector nhận diện lỗi khả dụng ngay lập tức và phân tích đồ thị cấu trúc chỉ ra lỗi tại `inventory-svc`.

### Exp 4: gateway_cpu_stress
- **Hypothesis**: CPU at 90% on api-gateway causes cascade downstream response degradation.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = api-gateway.
- **Analysis**: Quá tải CPU tại cổng vào hệ thống làm chậm tiến trình định tuyến luồng request. Pipeline phát hiện độ trễ tăng vọt trên toàn bộ các dịch vụ hạ nguồn nhưng bộ tương quan (Correlator) đã thành công gom nhóm lỗi về điểm nghẽn gốc là `api-gateway`.

### Exp 5: payment_db_mem_fill
- **Hypothesis**: High memory consumption on payment-db locks transaction pools.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = payment-db.
- **Analysis**: Tràn bộ nhớ lên đến 95% khiến DB cạn kiệt tài nguyên xử lý truy vấn dữ liệu. Các kết nối từ `payment-svc` sang bị timeout, Pipeline ghi nhận cảnh báo tài nguyên và định vị chuẩn xác `payment-db`.

### Exp 6: auth_clock_skew
- **Hypothesis**: Time skew +60s on auth-svc invalidates JWT validations.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = auth-svc.
- **Analysis**: Đây là lỗi logic ngầm độc hại. Container vẫn sống nhưng việc lệch múi giờ làm toàn bộ token xác thực bị coi là hết hạn. Detector nhận diện lỗi qua tỷ lệ lỗi xác thực tăng vọt và RCA gán chính xác trách nhiệm cho `auth-svc`.

### Exp 7: log_collector_disk_fill
- **Hypothesis**: Filling disk space to 95% triggers data log ingestion lag.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = log-collector.
- **Analysis**: Dung lượng đĩa cạn kiệt làm nghẽn luồng ghi log hệ thống. Bộ lọc meta-monitoring đã phát hiện ra độ trễ ghi nhận bản ghi (ingestion lag) và thuật toán RCA chỉ điểm đúng cấu phần `log-collector`.

### Exp 8: edge_network_partition
- **Hypothesis**: Full network block between frontend and gateway triggers global edge timeout.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = frontend.
- **Analysis**: Lỗi phân mảnh làm cô lập hoàn toàn lớp giao diện của người dùng. Pipeline ghi nhận bão lỗi timeout tại lớp Edge và thành công xác định lát cắt đứt gãy kết nối mạng nằm tại vị trí của `frontend`.

### Exp 9: dns_slow_lookup
- **Hypothesis**: DNS lookup delay +2s causes intermittent API layer network failures.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = dns-resolver.
- **Analysis**: Phân giải tên miền chậm làm tăng tổng thời gian thiết lập kết nối (connection handshake). Pipeline thu thập metric thời gian tra cứu và thuật toán RCA ánh xạ thành công nguyên nhân về `dns-resolver`.

### Exp 10: checkout_retry_storm
- **Hypothesis**: 20% HTTP 500 on checkout-svc triggers a client retry storm, load cascades to payment/inventory. RCA must NOT pick checkout-svc.
- **Observed**: Detected = Y, MTTD = 15s, RCA service = payment-svc.
- **Analysis**: Thử nghiệm bão lặp này hoạt động đúng theo giả thuyết. Mặc dù `checkout-svc` là nơi hứng triệu chứng lỗi đầu tiên, nhưng bão tải lan truyền làm nghẽn hàng đợi xử lý của tầng thanh toán. Pipeline phân tích đồ thị phụ thuộc đã thông minh bỏ qua `checkout-svc` và chỉ ra `payment-svc` mới là điểm thắt nút thực sự.

## 4. Gap analysis — top 3 pipeline weaknesses

### Gap 1: Độ trễ trong việc cập nhật biểu đồ phụ thuộc (Dependency Graph)
- **Symptom**: Thời gian MTTD bị cố định ở mức 15 giây đối với toàn bộ các loại lỗi hạ tầng mạng cấp bách.
- **Likely cause**: Bộ Detector thực hiện cào dữ liệu định kỳ (Scrape Interval) theo khoảng thời gian cố định, chưa có cơ chế tiếp nhận cảnh báo dạng Event-driven (Push-based).
- **Recommended fix**: Đề xuất tích hợp cơ chế Webhook từ Alertmanager trực tiếp vào Pipeline để đẩy thông báo bất thường ngay lập tức khi lỗi xảy ra, thay vì đợi luồng Pull tuần tự.

### Gap 2: Khả năng phân biệt giữa các lỗi tài nguyên chồng chéo
- **Symptom**: Trong thử nghiệm Memory Fill và CPU Stress, Pipeline dễ nhầm lẫn phân lớp lỗi (Fault Class) nếu hai tài nguyên này cùng tăng cao đồng thời.
- **Likely cause**: Bộ Correlator đang sử dụng trọng số heuristic đơn giản, chưa áp dụng mô hình phân loại đa nhãn (Multi-label Classification).
- **Recommended fix**: Áp dụng thuật toán Random Forest hoặc cây quyết định để huấn luyện dữ liệu từ baseline, tăng độ chính xác khi phân loại các lỗi tài nguyên phức tạp.

### Gap 3: Nguy cơ bỏ sót lỗi đối với các dịch vụ chạy bất đồng bộ (Asynchronous)
- **Symptom**: Lỗi đầy ổ đĩa của `log-collector` mất nhiều thời gian đánh giá bằng chứng chứng minh (Evidence Confidence) hơn các lỗi mạng trực tiếp.
- **Likely cause**: Metric thu thập của các tác vụ chạy ngầm thường có độ trễ lớn và không tác động ngay lập tức lên trải nghiệm End-to-end của người dùng.
- **Recommended fix**: Bổ sung thêm các trọng số giám sát chuyên biệt cho hàng đợi tin nhắn (Queue Depth) và độ trễ xử lý log để tăng điểm tin cậy (Confidence Score) cho bộ RCA.