# Detection Approach — DESIGN.md

## Approach 
Hệ thống sử dụng phương pháp **Hybrid Rule-based Thresholds & Keyword Matching** (Kết hợp ngưỡng tĩnh thông minh trên Metrics và Khớp từ khóa trên Logs) trong một kiến trúc xử lý Streaming Data thời gian thực.

## Tại sao chọn approach này
Trong môi trường On-call production tốc độ cao, tiêu chí tiên quyết là **Tốc độ xử lý (Low Latency)** và **Độ chính xác cao (Low False Alarm)**. 
- Việc tính toán toán học phức tạp liên tục trên dữ liệu streaming có tốc độ tick cực ngắn (`--speed 30x/100x`) dễ gây hiện tượng nghẽn luồng xử lý (Block Event Loop) của FastAPI, dẫn đến rớt gói tin (ConnectTimeout).
- Tiếp cận bằng cách cấu hình các ngưỡng biên an toàn tối hạn (Hard Thresholds) kết hợp correlation (đối chiếu chéo) trực tiếp giữa Log mang dấu hiệu đặc trưng (`outofmemory`, `circuit breaker`, `overloaded`) giúp pipeline đưa ra quyết định cảnh báo ngay lập tức mà không tiêu tốn tài nguyên tính toán.

## Cách hoạt động
Hệ thống hoạt động theo cơ chế Single-point Trigger thông qua 4 bước:
1. **Ingest**: Tiếp nhận Payload lai (Hybrid Payload) chứa cả thông số hạ tầng (Metrics) và thông điệp ứng dụng (Logs) qua phương thức HTTP POST `/ingest`.
2. **Parsing & Normalization**: Bóc tách, tính toán tỷ lệ phân bổ bộ nhớ (`mem_utilization`) và gộp toàn bộ các log messages thành một chuỗi văn bản không phân biệt hoa thường (`log_dump`).
3. **Correlation Logic**: Đối chiếu dữ liệu thực tế với kịch bản sự cố ShopX:
   - *Memory Leak*: RAM tăng tuyến tính vượt mức an toàn (> 75%) hoặc xuất hiện lỗi Heap OutOfMemory từ hệ thống máy ảo JVM.
   - *Dependency Timeout*: Latency nhảy vọt (> 500ms) kèm tỷ lệ rớt kết nối ngoại vi tăng mạnh (> 15%) hoặc phát hiện tín hiệu từ Circuit Breaker.
   - *Traffic Spike*: Lưu lượng requests vọt quá ngưỡng chịu tải thông thường (> 300 RPS) đi kèm hiện tượng nghẽn hàng đợi (`queue_depth > 40`).
4. **State Lock & Alerting**: Khi phát hiện bất thường, ghi chính xác một bản ghi JSON vào `alerts.jsonl` và lập tức kích hoạt khóa trạng thái `ALERT_FIRED = True` nhằm triệt tiêu hoàn toàn vấn đề Spam Alert trong suốt thời gian sự cố leo thang.

## Parameters đã chọn
- `mem_utilization > 0.75` (75%): Tránh các đỉnh nhọn nhiễu (RAM thông thường dao động ở mức dưới 50%), chỉ kích hoạt khi bộ nhớ có dấu hiệu cạn kiệt nghiêm trọng.
- `latency > 500.0` và `timeout_rate > 15.0`: Ngăn chặn việc báo động sai khi mạng chỉ bị lag cục bộ trong 1-2 giây, đảm bảo dịch vụ upstream thực sự gặp lỗi cascade.
- `rps > 300.0` và `queue_depth > 40`: Xác định chính xác trạng thái quá tải hệ thống, vượt quá năng lực xử lý bình thường của container (baseline thông thường < 160 RPS).

## Cải thiện nếu có thêm thời gian
- Tích hợp thêm thuật toán toán học không phụ thuộc phân phối dữ liệu chuẩn như **Modified Z-Score (dựa trên Median và MAD)** nhưng được tối ưu hóa xử lý song song thông qua `BackgroundTasks` hoặc hàng đợi nội bộ (Internal Queue) để không block luồng xử lý request chính, từ đó có một hệ thống ngưỡng động (Dynamic Threshold) hoàn hảo tự thích ứng với chu kỳ ngày/đêm (Diurnal Pattern) của ShopX.
- Bổ sung cơ chế tự động mở khóa (Auto-recovery / Reset state) khi tất cả các thông số hệ thống quay lại vùng an toàn liên tục trong một khoảng thời gian nhất định (Cool-down window).