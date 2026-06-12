# Eight-Week Migration Plan

## Hoạt động chi tiết theo từng tuần

### Tuần 1 - Tuần 2: Thiết lập hạ tầng OpenTelemetry & Cấu hình song song (Mirroring)
* **Hành động:** Triển khai OpenTelemetry Collector chạy song song bên cạnh Datadog Agent cũ trên toàn bộ các Host của 10 dịch vụ. Cấu hình ứng dụng xuất dữ liệu đồng thời ra cả 2 Endpoint.
* **Đảm bảo không mất giám sát (No-Blackout):** Hệ thống Datadog và Splunk cũ vẫn giữ vai trò là hệ thống cảnh báo và theo dõi chính trong suốt giai đoạn này.
* **Cơ chế khẩn cấp (Rollback Path):** Nếu OTel Collector gây ra hiện tượng nghẽn mạng hoặc tiêu tốn CPU quá mức trên các máy chủ ứng dụng, tiến hành gỡ lệnh triển khai (Uninstall DaemonSet) qua lệnh Helm/Kubectl trong vòng 5 phút để đưa hệ thống về nguyên trạng.
* **Go/No-Go Gate 1:** OTel Collector thu thập thông suốt toàn bộ dữ liệu mẫu trên môi trường kiểm thử (Staging Cluster) với mức độ tiêu hao tài nguyên phần cứng nghiêm ngặt dưới mức quy định `< 5% CPU` và `< 512MB RAM`.

### Tuần 3 - Tuần 4: Chuyển dịch luồng Metrics & Tái cấu trúc Dashboards tập trung
* **Hành động:** Chuyển hướng luồng dữ liệu Metrics từ OTel Collector đổ về hệ thống lưu trữ **Grafana Mimir**. Tiến hành dịch chuyển và biên dịch các biểu đồ giám sát cốt lõi từ Datadog sang Grafana Cloud làm màn hình theo dõi chính.
* **Đảm bảo không mất giám sát (No-Blackout):** Datadog Monitors vẫn được bật để thực hiện quét lỗi ngầm song song.
* **Cơ chế khẩn cấp (Rollback Path):** Nếu dữ liệu hiển thị trên Grafana bị sai lệch hoặc mất gói tin, kỹ sư lập tức quay trở lại sử dụng UI của Datadog để theo dõi hệ thống, đảm bảo không gián đoạn tầm nhìn vận hành.
* **Go/No-Go Gate 2:** Tái lập thành công tối thiểu 95% số lượng bảng điều khiển quan trọng và độ trễ phản hồi khi truy vấn dữ liệu (Query Latency) trên Grafana duy trì ở mức mượt mà `< 2s` ở phân vị p99.

### Tuần 5 - Tuần 6: Chuyển dịch cấu trúc Logs & Kích hoạt Tail-Based Sampling Tracing
* **Hành động:** Kích hoạt bộ lọc Tail-based Sampling tại OTel Collector để phân loại Traces và đẩy về **Grafana Tempo**. Đồng thời, cắt luồng logs từ Splunk Cloud chuyển hướng nạp dữ liệu trực tiếp vào hệ thống **Grafana Loki** (Đồng bộ cơ chế tự động đẩy file nén thô lưu trữ dài hạn vào AWS S3 sau 15 ngày).
* **Cơ chế khẩn cấp (Rollback Path):** Giữ nguyên cấu hình Splunk Forwarder chạy ngầm. Nếu luồng Loki bị quá tải nạp dữ liệu, thực hiện cập nhật lại ConfigMap của OTel Collector để tái mở cổng đẩy logs ngược lại Splunk Cloud trong vòng dưới 10 phút.
* **Go/No-Go Gate 3:** Hệ thống bắt và lưu trữ thành công 100% các vết trace sự cố lỗi thực tế, đồng thời kiểm tra ngẫu nhiên dữ liệu logs lưu kho trên AWS S3 đảm bảo khả năng đọc ghi cấu trúc chuẩn hóa đạt tỷ lệ thành công 100%.

### Tuần 7 - Tuần 8: Tích hợp Alertmanager, Đào tạo On-Call & Chấm dứt hợp đồng cũ
* **Hành động:** Đấu nối hệ thống cảnh báo từ Mimir và Loki tập trung về **Prometheus Alertmanager** để thực hiện gom cụm thông minh, sau đó chuyển tiếp tín hiệu webhook tinh gọn sang **PagerDuty**. Tổ chức các buổi diễn tập sự cố giả lập (Game Days) để đội ngũ on-call làm quen giao diện mới. Tiến hành tắt hoàn toàn các Agent cũ và gửi thông báo dừng gia hạn hợp đồng đúng hạn cho nhà cung cấp Splunk (đảm bảo tuân thủ nghiêm ngặt điều khoản thông báo trước 90 ngày của hợp đồng).
* **Cơ chế khẩn cấp (Rollback Path):** Toàn bộ các luật cảnh báo cũ trên Datadog vẫn được duy trì ở trạng thái im lặng (Silenced). Nếu Alertmanager gặp trục trặc không gửi được tin nhắn cứu hộ, lập tức gỡ bỏ trạng thái im lặng trên Datadog để hệ thống cũ tái phát tín hiệu báo động trực tiếp sang PagerDuty.
* **Go/No-Go Gate 4:** 100% kỹ sư trực ban vượt qua bài kiểm tra thực hành cứu hộ sự cố độc lập trên giao diện Grafana mới mà không cần mở bất kỳ công cụ cũ nào hỗ trợ.