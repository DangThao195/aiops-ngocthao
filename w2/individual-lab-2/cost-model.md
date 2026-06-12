# Observability Cost Model

## Current vs. Target Budget Comparison

| Line Item | Tool Today | Cost Today | Tool Target | Cost Target | Unit Driver | Scale Assumptions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **APM / Tracing** | Datadog Pro | $11,800 | Grafana Tempo | $2,800 | GB Ingested | 295 Hosts -> Tail-sampling giữ 100% lỗi, 1% thành công. |
| **Infra Metrics** | Datadog Pro | $5,400 | Grafana Mimir | $1,800 | Host-hours | 300 Hosts. |
| **Custom Metrics** | Datadog | $2,200 | Grafana Mimir | $400 | Active series | OTel Filter loại bỏ `customer_id` vô nghĩa trước khi nạp dữ liệu. |
| **Datadog Logs** | Datadog Logs | $1,800 | Tắt bỏ (Gom luồng) | $0 | Events indexed | Hợp nhất luồng logs trực tiếp về Loki. |
| **Long-tail Log Storage** | Splunk Cloud | $13,900 | Grafana Loki + S3 | $3,800 | GB/day + S3 storage| 52 GB/ngày, 15 ngày Hot Tier tại Loki, 30 ngày Cold Tier S3. |
| **Incident Routing** | PagerDuty | $3,900 | PagerDuty | $2,100 | User seats | Cắt giảm từ 65 xuống 35 Seats (Chỉ giữ kỹ sư Core On-call trực tiếp). |
| **Dashboards Visual** | Grafana Cloud | $1,050 | Grafana Enterprise | $3,200 | Active Users / Sub | Nâng cấp lên gói Enterprise tập trung giao diện cho toàn bộ công ty. |
| **Synthetic Checks** | DD Synthetics | $1,360 | Grafana Synthetics | $600 | API Checks | Tối ưu hóa tần suất, gom cụm từ 270 xuống 150 checks cốt lõi. |
| **Tracing Premium** | DD APM Pro | $300 | Tắt bỏ | $0 | Add-on | Đã tích hợp trong cấu trúc lõi của Tempo. |
| **Status Page** | Statuspage.io | $290 | Grafana Statuspage | $200 | Subscription | Sử dụng tính năng có sẵn trong hệ sinh thái mới. |
| **TOTAL** | | **~$42,000** | | **~$17,900** | | **Tiết kiệm thực tế: 57.3%** |

## Sensitivity Analysis (Dòng nhạy cảm ngân sách)

* **Thành phần dễ phá vỡ ngân sách nhất:** **Dung lượng nạp Logs (Log Ingestion Rate) vào Grafana Loki** nếu dữ liệu hệ thống tăng trưởng nhanh đột biến gấp 2 lần (104 GB/ngày).
* **Hệ quả kịch bản:** Nếu không kiểm soát, chi phí nạp dữ liệu của Loki sẽ tăng tuyến tính trực tiếp thêm ~$3,800/tháng, đe dọa hạn mức chi phí mới.
* **Biện pháp phòng vệ kiến trúc:** Cấu hình bộ giới hạn tốc độ nạp cứng (`Rate-limiting processor`) và áp dụng bộ lọc loại bỏ dòng chứa từ khóa `DEBUG` dư thừa ngay tại file cấu hình biên của **OpenTelemetry Collector** trên các máy chủ ứng dụng trước khi truyền tải qua internet.