# Postmortem: Cloudflare WAF Catastrophic Backtracking Outage (2026-06-17)

## Summary
Vào lúc 14:49 UTC, hệ thống phân phối traffic biên gặp sự cố sập nguồn trên diện rộng do một quy tắc cấu hình Web Application Firewall (WAF) chưa tối ưu được áp dụng. Quy tắc này chứa một chuỗi biểu thức chính quy (Regex) không an toàn, kích hoạt trạng thái Catastrophic Backtracking khi xử lý các chuỗi đầu vào đặc biệt từ người dùng. Sự cố gây tê liệt hoàn toàn luồng xử lý CPU của dịch vụ API Edge, đẩy thời gian phản hồi p99 lên vô hạn và làm gián đoạn cục bộ 100% dịch vụ gọi từ bên ngoài trong vòng 8 phút 52 giây. Hệ thống phục hồi hoàn toàn sau khi tiến trình container được khởi động lại và gỡ bỏ cấu hình rule WAF lỗi.

## Impact
- **Users affected:** 100% người dùng tiếp cận qua Gateway biên bị ảnh hưởng gián đoạn kết nối.
- **Services affected:** `cloudflare_regex_2019-api`, `payment-svc` (bị nghẽn mạch gián tiếp).
- **Revenue/SLA impact:** Vi phạm nghiêm trọng SLO p99 Latency (< 200ms) trong vòng 30 ngày; gây tổn thất trực tiếp đến cam kết SLA với đối tác B2B.
- **Duration:** 1781683668 → 1781684200 (532 giây ≈ 8 phút 52 giây).

## Timeline (UTC)
Toàn bộ dòng thời gian sự kiện được đồng bộ hóa từ hệ thống giám sát và trích xuất từ `timeline.json`:

| UTC | Event |
|-----|-------|
| 2026-06-17 14:43:20 | Hệ thống hoạt động ở trạng thái ổn định (Steady-State), p99 latency < 200ms, CPU tiêu thụ < 10%. |
| 2026-06-17 14:47:48 | Quy trình triển khai tự động áp dụng quy tắc cấu hình WAF mới trên diện rộng trên môi trường production thông qua script cấu hình. |
| 2026-06-17 14:47:50 | Quy tắc WAF chứa chuỗi Regex chưa tối ưu (Evil Regex) chính thức hoạt động ngầm tại cổng kết nối 8888. |
| 2026-06-17 14:48:20 | Hệ thống bắt đầu tiếp nhận các chuỗi ký tự payload lạ liên tục từ phía client thông qua các yêu cầu tìm kiếm đầu vào công cộng. |
| 2026-06-17 14:48:35 | Thuật toán kiểm tra Regex rơi vào trạng thái lặp tổ hợp cấp số nhân (Catastrophic Backtracking), chiếm dụng toàn bộ các luồng xử lý và vắt kiệt 100% tài nguyên CPU của container api. |
| 2026-06-17 14:49:00 | Chỉ số bão hòa tài nguyên kích hoạt cảnh báo: Hệ thống Prometheus ghi nhận chỉ số `container_cpu_usage_seconds_total` vượt ngưỡng an toàn nghiêm trọng. |
| 2026-06-17 14:50:00 | Ứng dụng FastAPI phản hồi chậm nghiêm trọng, các yêu cầu kiểm tra giả lập từ bên ngoài (Synthetic Probes) báo lỗi Timeout mạch kết nối diện rộng. |
| 2026-06-17 14:52:23 | Cảnh báo đầu tiên từ Pipeline AIOps kích hoạt trễ tại port 8000, ghi nhận bất thường tăng vọt latency tại dịch vụ downstream `payment-svc`. |
| 2026-06-17 14:56:40 | Hành động khắc phục (Mitigation): Quy trình vận hành thực hiện khởi động lại cụm container để xóa bỏ triệt để cấu hình rule WAF lỗi, đưa mức tiêu thụ CPU và Latency về baseline an toàn. |

## Root cause
Quy trình kiểm thử và tích hợp liên tục (CI/CD Pipeline) đã cho phép một biểu thức chính quy (Regex) có độ phức tạp thời gian tăng theo cấp số nhân (ReDoS vulnerability) được triển khai trực tiếp lên môi trường production mà không qua bộ màng lọc quét kiểm tra tĩnh (Static Regex Analyzer) hoặc giới hạn thời gian thực thi (Regex execution timeout guardrails).

## Contributing factors
1. Cơ chế giám sát hiện tại của Pipeline AIOps chỉ cấu hình lắng nghe các chỉ số lỗi HTTP và Latency, hoàn toàn không có cảm biến Anomaly Detection dựa trên chỉ số bão hòa tài nguyên phần cứng (Container CPU/RAM Saturation) tại thời gian thực.
2. Hệ thống áp dụng cấu hình quy tắc mới đồng loạt trên toàn bộ hạ tầng (Global Atomic Push) thay vì áp dụng cơ chế triển khai cuốn chiếu chia nhỏ vùng ảnh hưởng (Canary Rollout từng phân vùng).

## Detection
- **How was it detected?** Sự cố được phát hiện thủ công thông qua việc kiểm tra log hệ thống và Synthetic Probes bên ngoài, kết hợp một cảnh báo trễ từ Pipeline AIOps bắn về.
- **MTTD:** 228 giây (Từ lúc CPU vọt lên 100% lúc 14:48:35 đến khi alert bắn ra lúc 14:52:23).
- **Pipeline gaps observed during reproduction:**
  - **Gap 1 (Detector Blindspot):** Bộ dò tìm (Detector) của AI hoàn toàn bỏ qua chỉ số bão hòa CPU của Container, dẫn đến việc lọt lưới sự cố ReDoS đóng băng luồng xử lý và chỉ phát hiện gián tiếp khi ứng dụng đã sập dây chuyền sinh lỗi trễ (Latency).
  - **Gap 2 (RCA Hallucination):** Bộ phân tích nguyên nhân gốc rễ (RCA) sử dụng thuật toán đếm số lượng lỗi ngây thơ (Count-based ranking), dẫn đến việc chẩn đoán sai lệch nguyên nhân gốc sang dịch vụ downstream `payment-svc` vì dịch vụ này chịu tầng ứng dụng nén dòng (Retry Storm) phát ra lượng log lỗi nhiều nhất.

## Response
- **First responder action:** Kỹ sư vận hành thực hiện kiểm tra Docker Desktop, phát hiện container `cloudflare_regex_2019-api-1` chiếm dụng 100% CPU nền, tiến hành cách ly và chạy lệnh cưỡng bức khởi động lại container (`docker compose restart`).
- **Time to mitigate:** 8 phút 52 giây.
- **Time to fully resolve:** 8 phút 52 giây (Hệ thống phục hồi baseline ngay sau khi rule lỗi bị triệt tiêu).

## Action items
| # | Action | Owner | Type | ETA |
|---|--------|-------|------|-----|
| 1 | Triển khai công cụ quét ReDoS tĩnh tự động (nhux `safe-regex`) vào Pipeline kiểm thử code trước khi cho phép merge PR | Dev-Team | preventive | 2026-06-30 |
| 2 | Nâng cấp Pipeline AIOps, bổ sung bộ dò tìm Ensemble Anomaly Detection theo dõi chỉ số bão hòa CPU/RAM của container | SRE-Team | detective | 2026-07-05 |
| 3 | Tái cấu trúc bộ phân tích RCA sang mô hình Topology-Aware để nhận biết cấu trúc đồ thị phụ thuộc của dịch vụ, tránh lỗi chẩn đoán sai lệch hạ tầng | AIOps-Team | mitigation | 2026-07-15 |