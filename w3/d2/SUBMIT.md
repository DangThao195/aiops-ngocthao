# W3-D2 Submission 

## 3 things I learned about my AIOps pipeline
1. Em hiểu được tầm quan trọng cốt lõi của việc chuẩn hóa cấu trúc nhãn (Labels) trong Prometheus; nếu thiếu nhãn phân nhóm, hệ thống giám sát dữ liệu sẽ dễ bị lỗi phân mảnh và trả về mảng rỗng.
2. Em học được cách bộ toán tử phân tích đồ thị hoạt động trong việc bóc tách lỗi: hệ thống có khả năng bỏ qua các dịch vụ chỉ mang triệu chứng lỗi (Symptom Carrier) như trong kịch bản Retry Storm để tìm ra Root Cause thực sự nằm ở downstream.
3. Em nhận ra cơ chế đồng bộ thời gian (Time Window) giữa lúc bơm lỗi và lúc gửi yêu cầu phân tích RCA là yếu tố quyết định để thuật toán so khớp chính xác dữ liệu tĩnh (Baseline) và dữ liệu động khi hệ thống gặp sự cố.

## 1 fault I expected the pipeline to catch but it missed
- **Experiment**: Thực ra trong bài Lab giả lập này hệ thống của em đã may mắn bắt trọn cả 10/10 lỗi. Tuy nhiên, nếu ở môi trường production thật, em dự đoán lỗi Lệch múi giờ (`auth_clock_skew`) sẽ rất dễ bị bỏ sót.
- **Why I expected detection**: Vì lỗi này trực tiếp làm hỏng tiến trình xác thực bảo mật hệ thống, khiến khách hàng không thể mua sắm.
- **Why the pipeline missed (hypothesis)**: Hệ thống dễ bỏ sót vì các container và pod vẫn báo trạng thái sống (`up == 1`), tài nguyên CPU/RAM hoàn toàn bình thường, nếu bộ Detector không quét sâu vào tỷ lệ mã phản hồi chi tiết của API (`Token Invalid`) thì sẽ coi hệ thống vẫn hoàn toàn khỏe mạnh.

## 1 trade-off in pipeline design I want to rethink
- Em muốn tái tư duy về sự đánh đổi giữa **Tần suất cào dữ liệu (Scrape Interval)** và **Tải tài nguyên hệ thống**. Để đạt được thời gian phát hiện nhanh (MTTD thấp), em đã ép hệ thống cào liên tục mỗi 2 giây. Tuy nhiên, việc này tạo ra áp lực cực kỳ lớn lên băng thông mạng nội bộ và dung lượng lưu trữ của TSDB khi hệ thống mở rộng quy mô lên hàng trăm dịch vụ. Em muốn thiết kế lại theo cơ chế cào động (Dynamic Scrape): Giữ mức 15s ở trạng thái tĩnh và tự động tăng tốc lên 2s khi phát hiện tín hiệu bất thường từ phía người dùng (External Probe).

## Scoreboard summary
- **detected**: 10/10
- **rca_correct**: 10/10
- **mttd_p50**: 15s
- **false_alarms**: 0
- **verdict**: SUCCESS / ACCEPTED