## KẾT QUẢ PHÂN TÍCH SỰ CỐ HỆ THỐNG 

### 1. Phân tích Cluster chính (c-000-000)
- **Root Cause xác định:** `payment-svc` (Điểm số phân tầng cấu trúc đạt tối đa `1.0` tại mảng `graph_top3`).
- **Lý do kỹ thuật:** Nhờ việc hiệu chỉnh lại giải thuật cô lập đồ thị dựa theo nút lá (`out_degree = 0`) phối hợp sâu sát với dòng thời gian, hệ thống đã chỉ định chuẩn xác `payment-svc` là nguồn phát lỗi đầu tiên. Bản chất log thô ghi nhận dịch vụ này cạn kiệt connection pool lúc `09:44:02Z`, gây sụt giảm request dây chuyền lên các tầng upstream là `checkout-svc` và `edge-lb`. Tầng phân loại ngữ cảnh bốc nhãn lỗi của cụm này thành `ddos`, đồng bộ với sự cố lịch sử `INC-2026-03-20`.

### 2. Đánh giá độ tin cậy và Khả năng Auto-Remediation
- **Đánh giá:** Tuyệt đối không phê duyệt Auto-Remediation cho cụm lỗi này.
- **Lý do:** Điểm tin cậy (Confidence Score) của tầng phân loại Keyword Jaccard rớt thảm hại xuống mức cảnh báo nguy hiểm là `0.12`, và tầng TF-IDF cũng chỉ đạt `0.52`. Điểm số thấp kỷ lục này minh chứng hệ thống đang thiếu hụt trầm trọng các dữ kiện văn bản tương thích cao trong catalog lịch sử để đưa ra kết luận chắc chắn. Kích hoạt bất kỳ kịch bản tự động sửa lỗi nào (như cấu hình lại luật chặn WAF/Cloudflare) ở mức tin cậy này đều mang lại rủi ro False Positive cực cao, có thể gây gián đoạn truy cập của người dùng thật trên hệ thống GeekShop.

### 3. Case gây nhiễu dữ liệu không chắc chắn
Trường hợp mơ hồ nhất nằm ở việc bóc nhãn lỗi cho cụm `c-000-001` (`recommender-svc`). 
- Phiên bản **Keyword Jaccard** sau khi lọc bỏ từ dừng kỹ thuật đã giảm điểm sâu xuống `0.1` và gán nhãn `data_pipeline_lag` (theo `INC-2026-06-02`).
- Phiên bản **TF-IDF** lại định vị sự cố sang nhãn `bad_deploy` với mức tin cậy tốt hơn hẳn là `0.48` (theo mã `INC-2026-04-15`).
Sự không nhất quán này xảy ra bởi vì bản thân cảnh báo thô của `recommender-svc` chỉ có duy nhất một fingerprint là `cpu_utilization`. Khi các từ rác bị tước bỏ, chuỗi văn bản quá ngắn khiến thuật toán Jaccard bị sụp đổ phép tính toán tập hợp, trong khi TF-IDF vẫn nỗ lực tìm kiếm khoảng cách dựa trên vector tần suất từ nhưng kết quả mang tính chất phỏng đoán gần đúng.

### 4. So sánh với phần Bonus 2 (TF-IDF)
Quá trình nâng cấp bộ lọc từ dừng kỹ thuật (Technical Stop-words) đã tạo ra một bức tranh đối chiếu vô cùng rõ nét giữa hai giải thuật tìm kiếm sự cố:

| Mã cụm lỗi | Nhãn lỗi & Điểm số phiên bản Core (Keyword Jaccard) | Nhãn lỗi & Điểm số phiên bản Mở rộng (Bonus 2 - TF-IDF) |
| :--- | :--- | :--- |
| **c-000-000** | `ddos` (Confidence: **`0.12`**) | `ddos` (Confidence: **`0.52`**) |
| **c-000-001** | `data_pipeline_lag` (Confidence: **`0.10`**) | `bad_deploy` (Confidence: **`0.48`**) |
| **c-000-002** | `cache_cold_start` (Confidence: **`0.10`**) | `cache_cold_start` (Confidence: **`0.49`**) |

- **Nhận xét chuyên sâu từ thực nghiệm:** Việc làm sạch các token kỹ thuật đại trà (`ms`, `p99`, `warn`, `crit`) đã trực tiếp bộc lộ điểm yếu chết người của thuật toán Rule-based Jaccard. Khi tập hợp từ khóa bị thu hẹp, phép chia Giao/Hợp trở nên vô cùng nhạy cảm và sụt giảm điểm số một cách cực đoan về sát mức 0. 
Ngược lại, **Bonus 2 (TF-IDF)** chứng minh sự vượt trội hoàn toàn về mặt kiến trúc. Nhờ cơ chế chấm điểm phạt các từ xuất hiện phổ biến trên toàn bộ hệ thống bằng chỉ số IDF, các vector Cosine giữ được độ mịn, phân phối điểm đồng đều ổn định quanh mức `0.5`, phản ánh đúng bản chất ngữ nghĩa văn bản mà không bị phụ thuộc vào độ dài ngắn của chuỗi log.

**Kết luận:** Để đưa pipeline này vào môi trường production thực tế của GeekShop, giải pháp tối ưu bắt buộc phải là sử dụng TF-IDF làm cốt lõi phân loại ngữ cảnh, loại bỏ hoàn toàn cơ chế Jaccard thô sơ để tránh các kết quả sụt giảm điểm số cực đoan.