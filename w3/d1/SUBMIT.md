# W3-D1 Submission 

## 3 thứ em học được
1. Thấu hiểu sâu sắc cơ chế vận hành của thuật toán Khóa kép Multi-Window Multi-Burn-Rate (MWMBR). Việc sử dụng toán tử toán học `AND` giữa cửa sổ thời gian dài (đảm bảo tính nghiêm trọng của sự cố) và cửa sổ ngắn (đảm bảo sự cố vẫn đang diễn ra thực tế ngay hiện tại) giúp triệt tiêu hiện tượng báo động giả và tự động tắt alert ngay lập tức khi kỹ sư bấm nút fix xong lỗi hệ thống.
2. Nắm vững bẫy toán học của hiện tượng pha loãng dữ liệu lỗi trong các ô cửa sổ trượt dài (Rolling window 1h/6h) và cách điều phối, tinh chỉnh linh hoạt giữa hai biến số: Siết chặt mục tiêu SLO Target kết hợp hạ thấp ngưỡng Threshold kích hoạt để tìm ra điểm cân bằng tối ưu nhất cho hệ thống giám sát.
3. Nhận diện và phân biệt được các Anti-pattern kinh điển trong thực chiến SRE, ví dụ như việc lạm dụng chỉ số bão hòa hạ tầng phần cứng (CPU/Memory usage) làm chỉ số đo lường mức độ hạnh phúc của người dùng (SLI), học được cách chuyển dịch tư duy thiết kế đặt góc nhìn từ phía Client-side (RUM).

## 1 thứ vẫn chưa rõ
Cơ chế tự động tối ưu hóa (Auto-tuning) các tham số Burn Rate và SLO Target bằng các thuật toán học máy (Machine Learning) dựa trên sự biến động liên tục mang tính mùa vụ (Seasonality) của lưu lượng traffic thực tế theo thời gian thực, thay vì phải cấu hình thủ công các hằng số cố định trong file YAML.

## 1 trade-off trong SLO decision của em mà em không chắc
Để đạt được tốc độ phản ứng kỷ lục `mttd_delta_s: 0` và quét sạch hoàn toàn lỗi lọt lưới (`false_negative: 0`), em đã quyết định siết mục tiêu SLO của API lên mức rất cao là `99.7%` kết hợp hạ thấp ngưỡng kích hoạt Tier 1 xuống còn `2.0`. Sự đánh đổi này khiến hệ thống cảnh báo trở nên nhạy cảm ở mức tối đa. Trên môi trường sản xuất thực tế, cấu hình này có rủi ro sẽ biến thành một cỗ máy spam báo động, liên tục Page gọi kỹ sư trực ca dậy vào ban đêm nếu hệ thống gặp phải các đợt chập chập chờn mạng cực ngắn (micro-spikes) diễn ra liên tục.

## Validation report
- noise_reduction_pct: 72.7%
- mttd_delta_s: 0s
- false_negative: 0
- verdict: pass