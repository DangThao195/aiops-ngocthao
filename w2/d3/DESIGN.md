# DESIGN.md

## 1. Pipeline Architecture trong Endpoint
Hệ thống tiếp nhận mảng các Alert thô qua giao thức HTTP POST tại endpoint `/incident`. Dữ liệu di chuyển qua 3 tầng tuyến tính:
- Tầng 1 (Correlation): Gom các alert trùng khít về mặt thời gian (sử dụng cấu hình `gap_sec=120s` vì qua thống kê vận hành, các chuỗi lỗi cascade dây chuyền thường bùng phát mạnh mẽ nhất trong vòng 2 phút) và không gian mạng mạng lưới (`max_hop=2`).
- Tầng 2 (RCA): Áp dụng thuật toán so khớp trên Service Graph đầu vào để xác định thực thể lỗi gốc.
- Tầng 3 (LLM Enrichment): Sử dụng mô hình hóa ngôn ngữ để sinh báo cáo tường minh bằng ngôn ngữ tự nhiên.

## 2. Latency Budget Breakdown
Với ngân sách thời gian tổng thể cho toàn hệ thống là p99 <= 10s, quỹ thời gian tiêu hao được phân bổ như sau:
- Tầng 1 & 2 (Thuật toán đồ thị thuần túy): Chiếm tối đa 200ms nhờ dữ liệu cấu trúc Service Graph được cache sẵn trực tiếp trên RAM (In-memory state).
- Tầng 3 (LLM API Call): Chiếm phần lớn thời gian xử lý, dao động từ 1.5s - 3s tùy thuộc vào độ dài prompt sinh ra cũng như tốc độ phản hồi từ phía đối tác OpenAI.
- Overhead hệ thống (Validation dữ liệu đầu vào, Middleware ghi log): < 50ms.

## 3. Lựa chọn Framework & Trade-off
Em lựa chọn **FastAPI** thay vì Flask hay BentoML bởi các lý do cốt lõi:
- So với Flask: FastAPI hỗ trợ lập trình bất đồng bộ (`async/await`) nguyên bản, giúp xử lý các tác vụ I/O-bound (gọi LLM API bên ngoài) cực kỳ hiệu quả mà không gây nghẽn luồng xử lý (non-blocking). Ngoài ra, khả năng tự động bóc tách và validate bằng Pydantic giúp hệ thống miễn nhiễm với các request sai định dạng.
- So với BentoML: Hệ thống là một chuỗi pipeline kết hợp logic đồ thị cấu trúc và API gọi ngoài (LLM), không phục vụ (serve) một file weight model học máy truyền thống. BentoML sẽ mang lại quá nhiều cấu hình phức tạp không cần thiết cho non-ML workload này.

## 4. Production Concern: Fault Tolerance 
Mối bận tâm lớn nhất là tầng gọi LLM API bên ngoài có thể gặp tình trạng quá tải hoặc sập (Outage). Để xử lý, hệ thống triển khai:
- Thiết lập cứng mức cấu hình `timeout=5.0s` cho mọi cuộc gọi outbound tới OpenAI để tránh request bị treo vô hạn.
- Cơ chế Fallback thông minh: Nếu LLM lỗi, endpoint sẽ hạ cấp mượt mà bằng cách chỉ trả về kết quả phân tích từ thuật toán Đồ thị (Layer 2) đi kèm cờ thông báo, bảo toàn tính sẵn sàng cao cho dịch vụ.