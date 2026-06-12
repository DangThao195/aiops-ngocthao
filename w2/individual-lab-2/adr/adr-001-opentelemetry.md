# ADR-001: Chuyển đổi toàn bộ Tầng Thu thập sang Chuẩn mở OpenTelemetry Collector

## Context (Bối cảnh)
Hệ thống cũ cài đặt song song cả Datadog Agent và Splunk Universal Forwarder trên từng máy chủ. Kiến trúc này gây hao phí tài nguyên CPU/RAM hệ thống, tạo ra tình trạng dữ liệu bị cô lập hoàn toàn (Silos) và trói buộc chặt chẽ mã nguồn ứng dụng vào các nhà cung cấp thương mại (Vendor Lock-in).

## Decision (Quyết định)
Gỡ bỏ hoàn toàn Datadog Agent và Splunk Universal Forwarder trên 10 dịch vụ cốt lõi. Thay thế bằng một hệ thống thu thập duy nhất: **OpenTelemetry (OTel) Collector** triển khai dưới dạng Agent DaemonSet / Sidecar. Toàn bộ Metrics, Logs, Traces từ ứng dụng sẽ được xuất ra theo chuẩn giao thức mở OTLP.

## Alternatives Considered (Phương án cân nhắc thay thế)
1. **Giữ nguyên Datadog Agent và cấu hình chuyển tiếp dữ liệu sang bên thứ ba:** Bị bác bỏ vì Datadog tính phí bản quyền trên mỗi Agent phân phối rất cao ($40/host), không thể đạt mục tiêu cắt giảm chi phí của doanh nghiệp.
2. **Triển khai kết hợp FluentBit (cho Logs) và Prometheus Agent (cho Metrics):** Bị bác bỏ vì việc duy trì hai loại Agent mã nguồn mở khác nhau làm tăng gánh nặng quản lý cấu hình và không cung cấp tính năng liên kết sâu dữ liệu nội bộ.

## Consequences (Hệ quả)
* **Tích cực:** Giải phóng hoàn toàn nguy cơ Vendor Lock-in. Nếu thay đổi nhà cung cấp trong tương lai, chỉ cần chỉnh sửa file `.yaml` cấu hình exporter tại OTel Collector mà không thay đổi bất kỳ dòng code ứng dụng nào. Giảm tải tài nguyên chạy ngầm trên các host.
* **Tiêu cực:** Đội ngũ kỹ sư nền tảng phải đầu tư thời gian ban đầu để xây dựng lại file cấu hình định tuyến dữ liệu, thiết lập lại các biểu thức Regex để bóc tách cấu trúc Logs thô sang định dạng JSON chuẩn hóa.