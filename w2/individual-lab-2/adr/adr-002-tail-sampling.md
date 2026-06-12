# ADR-002: Áp dụng cơ chế Tail-Based Sampling cho hệ thống Distributed Tracing

## Context (Bối cảnh)
Hệ thống cũ áp dụng cơ chế lấy mẫu cố định 1% ở phía Client (Head-based Sampling) do rào cản chi phí lưu trữ lớn của Datadog. Điều này dẫn đến tình trạng các lỗi hiếm gặp hoặc độ trễ biên ở phân khúc p99 bị loại bỏ hoàn toàn trước khi kịp ghi nhận, khiến kỹ sư trực ban mất dấu vết cứu hộ sự cố và phải lục tìm logs thủ công vô cùng chậm chạp.

## Decision (Quyết định)
Cấu hình tính năng **Tail-Based Sampling** trực tiếp tại tầng OpenTelemetry Collector. Quy trình hoạt động: Toàn bộ 100% traces sinh ra từ hệ thống sẽ được lưu tạm thời vào bộ nhớ đệm (RAM) của Collector. Khi một luồng request hoàn tất giao dịch, hệ thống áp dụng các quy tắc lọc thông minh:
1. Nếu mã trạng thái trả về là Lỗi (HTTP Status `>= 500` hoặc lỗi kết nối DB) $\rightarrow$ Lưu lại **100%** toàn bộ trace.
2. Nếu thời gian xử lý kéo dài vượt ngưỡng p95 (Latency `> 1.5s`) $\rightarrow$ Lưu lại **100%** toàn bộ trace.
3. Các request thành công, phản hồi nhanh bình thường $\rightarrow$ Chỉ lấy mẫu ngẫu nhiên **1%** để vẽ biểu đồ xu hướng tổng quan.

## Alternatives Considered (Phương án cân nhắc thay thế)
1. **Duy trì Head-based Sampling và nâng tỷ lệ lấy mẫu lên 50%:** Bị bác bỏ ngay lập tức vì sẽ gây bùng nổ chi phí lưu trữ mạng lưới dữ liệu vượt gấp nhiều lần mức ngân sách tổng.
2. **Lưu trữ thô 100% toàn bộ Traces vào cụm Elasticsearch tự vận hành:** Bị bác bỏ do chi phí tài nguyên máy tính để duy trì năng lực ghi đọc dữ liệu khổng lồ này lớn hơn cả tiền thuê SaaS thương mại.

## Consequences (Hệ quả)
* **Tích cực:** Đảm bảo kỹ sư trực ban có thể tìm thấy mã vết trace lỗi cho mọi sự cố nghiêm trọng, xử lý triệt để điểm nghẽn ẩn của hệ thống, giảm MTTR xuống dưới 30%.
* **Tiêu cực:** Bộ nhớ đệm RAM tiêu thụ tại các OTel Collector Agent sẽ tăng cao hơn do phải lưu giữ tạm thời dữ liệu trace trong vài giây trước khi đưa ra quyết định lọc. Bắt buộc phải cấu hình cấu trúc bộ giới hạn bộ nhớ cứng (`memory_limiter processor`) để tránh lỗi quá tải hệ thống (OOM).