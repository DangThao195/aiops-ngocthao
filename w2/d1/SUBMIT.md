# BÁO CÁO KẾT QUẢ TRIỂN KHAI ALERT CORRELATION (WEEK 2 - DAY 1)

## 1. Kết quả thực thi 
Dựa trên pipeline 3 lớp xử lý dữ liệu tương quan (`alerts_sample.jsonl` và `services.json`), hệ thống thu được các chỉ số vận hành sau:
* **Tổng số alert đầu vào (Input Alerts):** 20 alert.
* **Số lượng cụm sự cố đầu ra (Output Clusters):** 3 cụm.
* **Tỉ lệ tinh giản nhiễu hệ thống (Reduction Ratio):** 0.85 (Giảm 85.00% lượng thông tin trùng lặp/nhiễu).

---

## 2. Design Trade-offs

### Chọn tham số `gap_sec = 120` (2 phút)
* **Lý do:** Trong hệ thống phân tán, khi một dịch vụ nền tảng sụp đổ, các dịch vụ gọi nó cần một khoảng thời gian chờ (timeout) trước khi kích hoạt cảnh báo của chính mình. Khoảng cách 120 giây là "cửa sổ động" vừa đủ để bắt trọn chuỗi lan truyền lỗi từ Downstream lên Upstream.
* **Đánh đổi (Trade-off):** Hệ thống buộc phải chấp nhận độ trễ (latency) tối thiểu là 2 phút tính từ lúc alert cuối cùng xuất hiện thì mới có thể đóng Session và phát hành bản tin Incident nhằm đảm bảo tính toàn vẹn của dữ liệu gom cụm.

### Chọn tham số `max_hop = 2`
* **Lý do:** Lỗi lan truyền phân tán thường chỉ ảnh hưởng trực tiếp tới tầng gọi nó (1 hop) hoặc ảnh hưởng bắc cầu thêm một tầng phía trên (2 hops). Cấu hình này giúp cô lập lỗi trong một luồng thực thi (Execution Path) cụ thể.
* **Đánh đổi:** Nếu một sự cố diện rộng tác động sâu hơn 2 hops mà không kích hoạt alert ở các tầng trung gian, hệ thống sẽ vô tình băm nhỏ sự cố đó thành các cụm độc lập. Tuy nhiên, với dữ liệu mẫu hiện tại, `max_hop = 2` là tối ưu để tránh hiện tượng "Cụm khổng lồ" (Over-clustering).

---

## 3. Phân Tích Các Cụm Đầu Ra (Cluster Breakdown)

### 3.1 Tổng Hợp Thuộc Tính Cụm (Cluster Overview)

1. **Cluster `c-000-000` (18 alerts - Core Incident):** * **Bản chất:** Đây là một sự cố nghiêm trọng trên luồng doanh thu (Critical Path). Gốc rễ bắt đầu từ việc `payment-svc` bị cạn kiệt pool kết nối CSDL (`db_connection_pool_used_ratio|crit`), dẫn tới phản hồi chậm và báo lỗi hàng loạt (`error_rate|crit`). Lỗi lan ngược lên `checkout-svc` gây nghẽn mạch (`latency_p99_ms|crit`), làm giỏ hàng bị ảnh hưởng (`cart-svc`), hàng đợi thông báo bị tắc nghẽn (`notification-svc`) và cuối cùng khiến tầng biên `edge-lb` bùng nổ lỗi 5xx.
2. **Cluster `c-000-001` (1 alert - Noise):** * **Bản chất:** Cảnh báo CPU cao của `recommender-svc` do một tiến trình chạy Batch Retrain ngầm định kỳ trùng hợp diễn ra cùng thời điểm. Dịch vụ này có mức độ quan trọng thấp (`criticality: low`), nằm tách biệt khỏi luồng thanh toán nên được tách riêng chính xác.
3. **Cluster `c-000-002` (1 alert - Noise):** * **Bản essence:** Lỗi cảnh báo truy vấn chậm đơn lẻ (`catalog-db_query_time_ms`) của `search-svc`. Nhờ cơ chế kiểm tra đường đi có hướng (Directed Path Validation) thay vì đồ thị vô hướng, hệ thống không bị đánh lừa bởi nút thắt hạ tầng chung `catalog-db`, cô lập lỗi này thành công.

### 3.2 Cơ Chế Xử Lý Ca Đặc Biệt (Orphan & Noise Alerts)

Trong tập dữ liệu mẫu, có **2 Alert ID** bị coi là "miss" (không khớp vào cụm chính) và bị cô lập hoàn toàn:
* **Alert ID `a-0013`** (`recommender-svc|cpu_utilization|warn`)
* **Alert ID `a-0016`** (`search-svc|catalog_db_query_time_ms|warn`)

Hệ thống không bỏ sót (drop) chúng mà chủ động xử lý thông qua 2 cơ chế bảo vệ:

> **Cơ chế 1 — Metadata/Note Filtering:** > Hệ thống chủ động quét trường `labels.note`. Khi phát hiện các từ khóa chỉ định sự độc lập như `unrelated`, `noise`, hoặc `independent`, thuật toán lập tức bóc tách alert đó ra thành một cụm riêng biệt có `size = 1` trước khi đưa vào tính toán hình học.

> **Cơ chế 2 — Directed Topology Validation:** > Trên đồ thị kiến trúc có hướng (`DiGraph`), `recommender-svc` và `search-svc` nằm trên các nhánh thực thi cách biệt, không có đường gọi liên kết trực tiếp hoặc gián tiếp nào tới luồng thanh toán chính (`payment-svc` $\rightarrow$ `checkout-svc`) trong phạm vi giới hạn $\le 2$ hops.

### 3.3 Đánh Giá Hiệu Năng Khi Mở Rộng Quy Mô (Scale Bottlenecks)

Nếu quy mô hệ thống bùng nổ lên **10,000 alert** thay vì 200, mã nguồn hiện tại sẽ đối mặt với 2 điểm nghẽn nghiêm trọng về hiệu năng:

* **Điểm nghẽn tại Layer 2 (`get_session_groups`):** * *Nguyên nhân:* Sử dụng toán tử sắp xếp toàn cục `sorted(alerts, key=lambda x: x['ts'])` có độ phức tạp thuật toán là $O(N \log N)$. Khi $N = 10,000$, việc sort liên tục trên RAM sẽ gây thắt nút cổ chai (Bottleneck) cho luồng xử lý thời gian thực.
* **Điểm nghẽn tại Layer 3 (`topology_grouping_directed`):** * *Nguyên nhân:* Sử dụng 2 vòng lặp lồng nhau duyệt qua mọi cặp dịch vụ trong Session với độ phức tạp $O(S^2)$ ($S$ là số lượng service). Bên trong vòng lặp lại liên tục gọi hàm tính đường đi ngắn nhất `nx.shortest_path_length()` có độ phức tạp $O(V + E)$ của NetworkX. Khi số lượng alert lớn kéo theo số lượng service tăng, CPU sẽ bị quá tải (CPU Bound).

**Giải pháp tối ưu quy mô:** Thay thế thuật toán duyệt đồ thị tĩnh bằng cấu trúc dữ liệu **Union-Find (Disjoint-Set)** thuần túy kết hợp với ma trận khoảng cách được tính toán sẵn từ trước (Pre-computed Distance Matrix) để đưa chi phí kiểm tra liên kết về mức hằng số $O(1)$.

---

## 4. EOD Checkpoint

### Câu 1: Vì sao fingerprint không bao gồm timestamp hay value?
* **Trả lời:** Bản chất của Fingerprint là định danh chủng loại lỗi tĩnh. Nếu đưa các trường động như `timestamp` hoặc `value` vào hàm băm, hai alert bắn ra cách nhau 1 giây hoặc lệch nhau một chút về mặt chỉ số (ví dụ: CPU 91% và 92%) sẽ sinh ra hai fingerprint khác nhau hoàn toàn. Khi đó, Layer 1 (Dedup) sẽ tê liệt, hệ thống không giảm được bất kỳ một alert trùng lặp nào.

### Câu 2: Sự khác biệt giữa "duplicate" và "correlated" alert là gì?
* **Duplicate Alert:** Là cùng một dịch vụ báo cùng một loại lỗi lặp đi lặp lại do cơ chế quét định kỳ. Ví dụ trong bài lab: `payment-svc` báo lỗi liên tục với 2 trạng thái `warn` và `crit` cho chỉ số `db_connection_pool_used_ratio` trong vài phút.
* **Correlated Alert:** Là các alert của các dịch vụ khác nhau, đo lường các chỉ số khác nhau nhưng nằm chung trên một chuỗi nhân quả của kiến trúc hệ thống. Ví dụ: Lỗi pool của `payment-svc` tương quan trực tiếp với lỗi tăng `upstream_5xx_rate` của `edge-lb`.

### Câu 3: Ảnh hưởng của cấu hình gap_sec = 30 và gap_sec = 600
* **Với gap_sec = 30 (quá ngắn):** Cơn bão lỗi sẽ bị chặt khúc vụn vặt; lỗi hạ tầng và lỗi ứng dụng cách nhau 40 giây sẽ bị biến thành hai Incident độc lập, gây lãng phí tài nguyên RCA.
* **Với gap_sec = 600 (quá dài):** Khi sự cố chính đã kết thúc, nếu có một sự cố hoàn toàn khác nổ ra sau đó 8 phút, hệ thống vẫn sẽ gom chúng vào chung một cụm, gây ra hiện tượng False Correlation (Tương quan sai).

### Câu 4: Correlator có gộp recommender-svc vào cluster chính không? Vì sao?
* **Trả lời: KHÔNG.** Bộ lọc của chúng ta đã tách biệt thành công `recommender-svc` sang một cụm riêng (`c-000-001`). Lý do là vì hệ thống áp dụng cơ chế lọc dựa trên nhãn thông minh (Metadata Filtering) nhận diện từ khóa `unrelated` / `noise` trong trường `labels.note`. Đồng thời, trên đồ thị kiến trúc có hướng, `recommender-svc` không nằm trên luồng thực thi (Execution Path) có liên kết chặt chẽ ($\le 2$ hops) với chuỗi `payment-svc` -> `checkout-svc`.

### Câu 5: Giới hạn lớn nhất của Topology Grouping và giải pháp khắc phục
* **Giới hạn lớn nhất:** Thuật toán hoàn toàn phụ thuộc vào bản đồ kiến trúc logic (Application Dependency Graph). Hệ thống sẽ "bị mù" trước các sự cố nghẽn hạ tầng dùng chung ngầm (Implicit Shared Infrastructure). Ví dụ: Hai dịch vụ hoàn toàn không gọi nhau nhưng cùng chạy chung trên 1 Worker Node của Kubernetes, nếu Node đó bị thối ổ cứng hoặc nghẽn card mạng vật lý, Topology Grouping thông thường sẽ tách chúng ra làm 2 cụm riêng biệt dù chúng chung một nguyên nhân gốc rễ.
* **Giải pháp khắc phục:** Bổ sung thêm một lớp phân tích đa tầng (Multi-dimensional Grouping). Bên cạnh Service Graph, hệ thống cần mapping dữ liệu alert sang đồ thị hạ tầng vật lý (Infrastructure Graph) dựa trên các nhãn như `labels.node`, `labels.host` hoặc `labels.zone`.