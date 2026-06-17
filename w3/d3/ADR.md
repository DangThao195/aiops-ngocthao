# ADR-002: Use Topology-Aware RCA over Count-Based Alert Ranking

## Status
Accepted

## Context
Qua thực nghiệm tái hiện sự cố Cloudflare 2019 ReDoS Outage, bộ phân tích nguyên nhân gốc rễ (RCA) hiện tại của nền tảng AIOps đã chẩn đoán sai lệch hoàn toàn thủ phạm (RCA Hallucination). Hệ thống chỉ chỉ mặt đặt tên được dịch vụ downstream `payment-svc` với độ tin cậy 0.92, trong khi nguyên nhân gốc nằm ở tầng API Edge (`cloudflare_regex_2019-api`). 

Sự sai lệch này xảy ra do thuật toán RCA hiện tại đang sử dụng mô hình xếp hạng theo số lượng cảnh báo (Count-based ranking): dịch vụ nào sinh ra nhiều lỗi hoặc log biến động lớn nhất sẽ bị coi là gốc rễ. Trong các kịch bản sập dây chuyền (Cascading Failure) kết hợp bão bùng yêu cầu gửi lại (Retry Storm), các dịch vụ phía sau luôn gánh chịu lượng lỗi khuếch đại lớn hơn rất nhiều so với điểm nghẽn ban đầu, làm mù hướng phân tích của kỹ sư trực on-call.

## Decision
Chúng ta sẽ chuyển đổi toàn bộ kiến trúc lõi của bộ phân tích RCA sang mô hình kết hợp Đồ thị cấu trúc phụ thuộc (Topology-Aware RCA) phối hợp phân tích trễ nhân quả thời gian (Causal-Lag Analysis via Granger Causality). Thuật toán mới bắt buộc phải tính toán trọng số ưu tiên cho các dịch vụ nằm ở thượng nguồn (Upstream-bias) và dò tìm dịch vụ phát sinh độ lệch chỉ số (Metric drift) sớm nhất trong chuỗi thời gian, thay vì chỉ đếm số lượng alert đơn thuần.

## Alternatives considered
1. **Count-based Alert Ranking (Giữ nguyên kiến trúc cũ)** — *Bị từ chối:* Cực kỳ nhanh và nhẹ về tính toán, nhưng hoàn toàn thất bại và đưa ra chẩn đoán sai lệch trong mọi kịch bản hệ thống phân tán bị sập dây chuyền (Cascading Failure).
2. **LLM-only Augmented RCA (Sử dụng hoàn toàn trí tuệ nhân tạo tạo sinh Generative AI)** — *Bị từ chối:* Có khả năng đọc log rất linh hoạt, nhưng rất dễ gặp hiện tượng ảo tưởng (Hallucination) với mức độ tự tin ảo lớn hơn 0.9 nếu tài liệu ngữ cảnh đầu vào không có cấu trúc sạch, chi phí gọi API đám mây cao.
3. **Graph PageRank Only (Áp dụng thuật toán xếp hạng đồ thị tĩnh)** — *Bị từ chối:* Nhận biết được cấu trúc kết nối của hệ thống biên, nhưng bỏ qua yếu tố nhân quả về mặt thời gian (vị trí lỗi xảy ra trước/sau), không phân biệt được biến động ngẫu nhiên với sự cố thực tế.

## Consequences
- **Positive:**
  - Khắc phục hoàn toàn lỗi chẩn đoán sai lệch trong các kịch bản sập dây chuyền tương tự như vụ Cloudflare 2019 hoặc vụ sập vòng lặp giám sát của Roblox 2021.
  - Tăng tốc độ cô lập vùng lỗi (MTTR), chỉ định chính xác dịch vụ thượng nguồn đang gặp sự cố bão hòa tài nguyên cho kỹ sư on-call trong vòng dưới 30 giây.
- **Negative:**
  - Tăng chi phí tài nguyên tính toán (Compute cost vọt lên đáng kể do thuật toán Granger Causality tính ma trận trên chuỗi thời gian có độ phức tạp $O(n \times lag\_window)$).
- **Risks introduced:**
  - Hệ thống phụ thuộc lớn vào tính chính xác của bản đồ đồ thị dịch vụ (Topology Graph). Nếu sơ đồ kiến trúc hạ tầng cập nhật chậm hoặc bị sai lệch, thuật toán RCA mới sẽ hoạt động không chính xác.
- **What gets locked in:**
  - Nền tảng bắt buộc phải duy trì một dịch vụ ngầm tự động cập nhật sơ đồ phụ thuộc (Dynamic Service Topology Discovery) thu thập từ Service Mesh hoặc dữ liệu Distributed Tracing.