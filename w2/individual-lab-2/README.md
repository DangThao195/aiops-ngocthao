# Kiến trúc Tái thiết kế Hệ thống Giám sát & Vận hành AIOps - GeekShop

Hồ sơ thiết kế này cung cấp giải pháp toàn diện nhằm giải quyết đồng thời hai ràng buộc cốt lõi từ CTO: Cắt giảm tối thiểu 40% chi phí vận hành (Đạt được 57.3% thực tế) và giảm thiểu thời gian xử lý sự cố MTTR xuống trên 30% thông qua việc ứng dụng chuẩn mở OpenTelemetry và hệ sinh thái lưu trữ phân cấp Grafana LGTM Stack.

## Bản đồ hướng dẫn đọc hồ sơ chấm điểm:
1. **`architecture-target.png`**: Sơ đồ kiến trúc luồng dữ liệu mục tiêu hiển thị rõ ràng 3 tín hiệu (Metrics, Logs, Traces) đi qua màng lọc OTel Collector và quy trình gom cụm cảnh báo của Alertmanager.
2. **`components.md`**: Bảng tổng hợp chi tiết lý do lựa chọn từng công nghệ thay thế và phân tích rủi ro hệ lụy nếu thay đổi ý định sau 6 tháng.
3. **`cost-model.md`**: Bảng tính toán tài chính minh bạch so sánh từng dòng hóa đơn cũ và mới kèm theo bài toán phân tích độ nhạy cảm của ngân sách.
4. **`adr/`**: Thư mục chứa 2 quyết định kỹ thuật cân não nhất về việc chuẩn hóa OpenTelemetry và cơ chế lấy mẫu dữ liệu vết tại biên (Tail-based Sampling).
5. **`migration-plan.md`**: Lộ trình chuyển đổi chi tiết trong vòng 8 tuần cụ thể, thiết lập sẵn các cửa chặn Go/No-Go và quy trình quay xe khẩn cấp (Rollback) cho từng giai đoạn cắt luồng dữ liệu.
6. **`risks.md`**: Ma trận quản trị 6 rủi ro kỹ thuật lớn nhất kèm theo định danh kỹ sư chịu trách nhiệm giảm thiểu rủi ro trực tiếp.
7. **`FINDINGS.md`**: Tài liệu phản biện chuyên sâu trả lời 5 câu hỏi kiến trúc cốt lõi và vạch ra chiến lược chạy thử nghiệm (POC) để xác minh tính khả thi của hệ thống đệm dữ liệu.