# SPEC: AIOps Mini-Platform Spec 

## 1. Platform overview
Nền tảng AIOps Mini-Platform được thiết kế nhằm mục đích tự động hóa chu trình giám sát, phát hiện bất thường, gom cụm cảnh báo đồng thời phân tích nguyên nhân gốc rễ (RCA) cho hệ thống vi dịch vụ (Microservices) chạy trên nền tảng Docker/Kubernetes. Phạm vi (Scope) cốt lõi của nền tảng bao gồm việc xử lý chuỗi thời gian metric từ Prometheus, gom nhóm log lỗi từ các gateway biên, và chỉ định dịch vụ gây lỗi thượng nguồn để tối ưu chỉ số MTTR cho kỹ sư trực on-call. Nền tảng không bao gồm (Non-scope) việc tự động sửa code hoặc tự động thay đổi cấu hình hạ tầng mà không có sự phê duyệt của con người.

## 2. SLO definition (from W3-D1)
Hệ thống áp dụng màng lọc giám sát cho 3 dịch vụ cốt lõi:
- **Target SLO:** 99.9% tính trên cửa sổ trượt 30 ngày (30-day rolling window).
- **SLI:** Tỷ lệ số request thành công (Mã HTTP không chứa lỗi 5xx và lỗi 429) phản hồi trong khoảng thời gian Latency < 200ms trên tổng số request đầu vào.
- **Error budget:** 0.1% tổng lưu lượng request trong tháng (Tương đương tối đa 30,000 request lỗi/tháng nếu traffic đạt 1M req/day).
- **Burn-rate alert tiers:**
  - *Tier 1 (Urgent Page):* Burn rate ≥ 14.4 trên cả 2 cửa sổ đồng thời 1h và 5m (Hành động: Bắn alert page trực tiếp kỹ sư SRE dậy lập tức).
  - *Tier 2 (Page):* Burn rate ≥ 6 trên cửa sổ 6h và 30m (Hành động: Bắn alert page).
  - *Tier 3 (Ticket):* Burn rate ≥ 1 trên cửa sổ 3 ngày và 6h (Hành động: Tự động tạo ticket xử lý vào giờ hành chính).

## 3. Detection + Correlation + RCA stack (from W1+W2)
- **Detector:** Thuật toán static threshold tích hợp bộ dò tìm bất thường chuỗi thời gian (percentile-based anomaly detection trên p99 latency), đầu vào từ Prometheus API, đầu ra xuất chuỗi JSON ghi nhận trạng thái bất thường.
- **Correlator:** Thuật toán gom cụm dựa trên khoảng cách thời gian (Temporal Correlation Window 5 phút), nhóm các alert phát sinh cùng thời điểm thành một Incident Cluster duy nhất để tránh spam alert fatigue.
- **RCA:** Kiến trúc Topology-Aware RCA kết hợp Granger Causality (Theo quyết định tại `ADR.md`), sử dụng nguồn dữ liệu đồ thị dịch vụ động, đầu ra chỉ mặt đặt tên duy nhất một dịch vụ gây lỗi kèm chỉ số tự tin (Confidence Score).

## 4. Reliability validation (from W3-D2)
- **Chaos run cadence:** Chạy tự động hàng tuần (Weekly Chaos Experiment) trên môi trường giống production (Production-like env).
- **Detected/total ratio target:** Mục tiêu AI phải phát hiện thành công ≥ 90% số lỗi chủ động bơm vào hệ thống.
- **Steady-state signal:** Sử dụng kết hợp External Synthetic Probes (Bot shell kiểm tra độc lập ngoài cluster gọi endpoint mỗi 5 giây) để đo lường chính xác trải nghiệm thực của người dùng không phụ thuộc vào log nội bộ.

## 5. Operational pattern (from W3-D3)
- **Postmortem template:** Quy chuẩn theo form mẫu Google SRE Blameless Template tại `postmortem_template.md`.
- **On-call rotation:** Mô hình trực xoay tua Tier-based On-call Rotation (Chia tầng kỹ sư trực dựa theo mức độ khẩn cấp của Alert Tier).
- **ADR repository:** Lưu trữ tập trung tại thư mục `/w3/d3/ADR.md` theo chuẩn format Nygard (2011).

## 6. Cost model (from W3-D3)
- **Monthly cost:** 4,125.0 USD/tháng (Chi tiết bao gồm hạ tầng compute, storage, và chi phí FTE Engineer).
- **Break-even avoided incidents/month:** Nền tảng đạt điểm hòa vốn kinh tế nếu giúp giảm thiểu thời gian sập nguồn thu hồi lại giá trị tài chính ròng $2,916.80 USD/tháng (ROI: 1.71, đạt trạng thái AMBER cho Small Infra). Chi tiết báo cáo chạy tự động được ghi nhận tại file nguồn `cost_model.py`.

## 7. Open risks
- **Risk 1:** Độ trễ tính toán của thuật toán Granger Causality lớn khi quy mô microservices mở rộng lên hàng nghìn dịch vụ (Severity: High $\rightarrow$ Mitigation: Áp dụng màng lọc phân vùng đồ thị theo vị trí logic).
- **Risk 2:** Hiện tượng ảo tưởng chẩn đoán (RCA Hallucination) nếu Service Mesh bị mất kết nối và không cập nhật được Sơ đồ đồ thị tĩnh (Severity: Medium $\rightarrow$ Mitigation: Tự động fallback sang mô hình Count-based kèm nhãn cảnh báo độ tin cậy thấp nếu đồ thị rỗng).