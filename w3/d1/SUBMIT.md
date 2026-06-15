# W3-D1 Submission

## 3 thứ em học được
1. Thấu hiểu sâu sắc cơ chế hoạt động của thuật toán Khóa kép (MWMBR) bằng cách kết hợp điều kiện `AND` giữa cửa sổ thời gian dài (đảm bảo tính nghiêm trọng của phốt lỗi) và cửa sổ ngắn (đảm bảo sự cố vẫn đang diễn ra thực tế), giúp giảm thiểu tối đa hiện tượng alert rác khi sửa xong lỗi hệ thống.
2. Hiểu rõ bẫy toán học của việc pha loãng dữ liệu lỗi trong các cửa sổ trượt dài (Rolling window 1h/6h) và cách điều phối, tinh chỉnh giữa hai biến số: Siết chặt SLO Target và Hạ thấp ngưỡng Threshold để tìm ra điểm cân bằng giúp hệ thống báo động nhạy bén nhất.
3. Nhận diện các Anti-pattern kinh điển trong SRE như việc sử dụng chỉ số bão hòa hạ tầng (CPU/Memory usage) làm chỉ số đo lường hạnh phúc của người dùng (SLI), học được cách tư duy thiết kế đặt góc nhìn từ phía Client-side (RUM).

## 1 thứ vẫn chưa rõ
Cơ chế tự động tối ưu hóa (Auto-tuning) các tham số Burn Rate bằng Machine Learning hoặc thuật toán thích ứng dựa trên sự thay đổi liên tục mang tính mùa vụ (Seasonality) của traffic thực tế, thay vì phải cấu hình cứng (Hard-coded) các ngưỡng hằng số trong file YAML.

## 1 trade-off trong SLO decision của em mà không chắc
Để đạt được mốc phản ứng thần tốc `mttd_delta_s: 0` và quét sạch lỗi lọt lưới (`fn: 0`), em đã quyết định siết SLO của API lên mức rất cao là `99.7%` kết hợp hạ thấp ngưỡng kích hoạt Tier 1 xuống `2.0`. Sự đánh đổi này khiến hệ thống trở nên cực kỳ nhạy cảm. Trên môi trường sản xuất thực tế, cấu hình này có rủi ro sẽ biến thành một "cỗ máy spam" báo động nếu hệ thống gặp phải các đợt micro-spike (mạng chập chờn nhẹ trong vài giây) diễn ra liên tục.

## Validation report
- noise_reduction_pct: 72.7%
- mttd_delta_s: 0s
- false_negative: 0
- verdict: pass