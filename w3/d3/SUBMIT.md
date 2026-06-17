# W3-D3 Submission

## Outage chosen
- ID: 3
- Name: Cloudflare WAF regex 2019-07-02
- Why this one: Tôi chọn kịch bản này vì muốn nghiên cứu sâu cách một lỗ hổng bảo mật/hiệu năng tầng ứng dụng như ReDoS (Regex Denial of Service) có thể âm thầm bóp nghẹt tài nguyên phần cứng, tạo ra hiện tượng sập dây chuyền (Cascading Failure) đánh lρευ toàn bộ các hệ thống giám sát truyền thống như thế nào.
- Failure mode: regex

## 3 thứ tôi học từ outage này
1. **CPU không phải là một SLI tốt:** CPU đạt ngưỡng bão hòa 100% chỉ là một tín hiệu Saturation, hệ thống hoàn toàn có thể chạy 100% CPU nhưng user vẫn thấy mượt hoặc ngược lại, do đó không bao giờ dùng chỉ số phần cứng để làm mục tiêu SLO cam kết trải nghiệm người dùng.
2. **Văn hóa Blameless cứu sống hệ thống:** Việc mổ xẻ sự cố không được tập trung vào việc phạt cá nhân, mà phải phân tích tại sao màng lọc kiểm thử tự động lại cho phép một chuỗi cấu hình nguy hiểm lọt ra môi trường production.
3. **Sự nguy hiểm của hiện tượng sập dây chuyền với AI:** Thuật toán AI nếu không có tư duy đồ thị (Topology) sẽ luôn chẩn đoán sai lệch (RCA Wrong) vì nó bị thu hút hoàn toàn bởi các dịch vụ downstream phát sinh nhiều tiếng ồn và log lỗi nhất khi mạch bị tắc nghẽn.

## 1 thứ pipeline của tôi sẽ vẫn miss nếu outage này xảy ra real
- **Pattern:** Vòng lặp giám sát phụ thuộc (Monitoring dependency loop).
- **Why miss:** Nếu hệ thống giám sát và con Bot AI chạy chung trên cùng cụm hạ tầng với dịch vụ lõi bị sập, toàn bộ pipeline sẽ bị mất kết nối dữ liệu (silent blackout) và không thể đưa ra bất kỳ cảnh báo hay phân tích RCA nào.
- **Mitigation idea:** Thiết lập một cụm Observability độc lập hoàn toàn (Out-of-band monitoring stack) đặt ở vùng hạ tầng riêng biệt để đảm bảo tính cô lập khi hệ thống chính sập nguồn.

## 1 quyết định trong ADR mà tôi không hoàn toàn chắc
Tôi chưa hoàn toàn chắc chắn về việc chấp nhận đánh đổi chi phí tài nguyên tính toán tăng theo cấp số mũ $O(n \times lag\_window)$ của thuật toán Granger Causality trong bản thiết kế `ADR.md`. Khi hệ thống microservices mở rộng lên quy mô lớn, việc tính toán ma trận chuỗi thời gian liên tục có thể vô tình vắt kiệt chính tài nguyên của cụm máy chủ giám sát, lặp lại vết xe đổ vòng lặp sập nguồn (Monitoring Dependency Loop).

## Cost model verdict cho stack của tôi
Dựa trên kết quả chạy thực tế từ kịch bản Thương mại điện tử Việt Nam (Scenario 3):
- **ROI:** 11.59 (Giá trị thu hồi vượt trội hoàn toàn so với vốn đầu tư).
- **Payback:** ~0.086 tháng (Chỉ mất khoảng chưa đầy 3 ngày chạy thực tế để hệ thống hoàn vốn nhờ giảm thiểu thời gian sập nguồn giờ Flash Sale).
- **Verdict:** GREEN — value clearly exceeds cost (Mô hình kinh tế chỉ ra giá trị cứu vãn giảm thiểu thời gian sập nguồn hoàn toàn vượt trội so với chi phí chi trả hạ tầng, khuyến nghị triển khai ngay lập tức lên môi trường thực tế).