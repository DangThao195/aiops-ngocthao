# SUBMIT.md

## 1. Latency budget của endpoint (p99)? Phase nào chiếm thời gian nhất?
- Latency budget thực tế của hệ thống giả lập đang đạt mức ~1.6 giây cho p99.
- Phase chiếm phần lớn thời gian nhất là LLM API Call (gọi sang OpenAI để tạo phần giải trình lý do và hành động gợi ý). Tác vụ này mang bản chất I/O-bound, phụ thuộc hoàn toàn vào đường truyền mạng Internet và độ trễ phản hồi từ nhà cung cấp bên thứ ba.

## 2. Endpoint xử lý 5 alert vs 500 alert — latency khác nhau thế nào? Linear scale hay có fixed cost?
- Latency giữa 5 alert và 500 alert sẽ có sự chênh lệch nhỏ nhưng không tăng theo dạng tuyến tính (Linear scale) mà đồ thị tăng trưởng sẽ dẹt dần nhờ có Fixed Cost.
- Lý do: Chi phí lớn nhất (Fixed Cost) là thời gian chờ mạng khi gọi LLM (mất cố định ~1.5s dù chuỗi văn bản dài hay ngắn). Tải tăng từ 5 lên 500 alert chỉ làm tăng nhẹ thời gian tính toán gom cụm (Correlation) trên RAM đồ thị ở CPU cỡ vài chục miligiây, hoàn toàn bị lu mờ bởi thời gian gọi API.

## 3. LLM provider down giữa lúc đang chạy. Hệ thống behave ra sao? Phương án dự phòng?
- **Hành vi hệ thống:** Nếu không bọc xử lý, hệ thống sẽ bị treo cho đến khi hết timeout mặc định và trả ra mã lỗi `500 Internal Server Error`, làm mất khả năng quan sát của đội SRE.
- **Phương án dự phòng (Graceful Degradation):** 
  1. Sử dụng khối lệnh `try-except` bao bọc lấy cuộc gọi LLM kèm cài đặt giới hạn thời gian ngắt kết nối `timeout=5s`.
  2. Khi bắt được lỗi ngoại lệ (Timeout/Provider Down), hệ thống kích hoạt chế độ chạy thuật toán đồ thị thuần túy (Graph-only mode): Điền các trường thông tin của LLM bằng thông tin mặc định (ví dụ: `reasoning: "LLM Service Unavailable - Falling back to graph analysis"`), nhưng vẫn trả về mã thành công `200 OK` chứa kết quả phân cụm lỗi ổn định từ Đồ thị.

## 4. /healthz và /readyz khác nhau gì? Khi nào dùng cái nào?
- `/healthz` (Liveness probe): Khảo sát xem tiến trình ứng dụng còn sống hay đã chết. Nếu endpoint này trả về lỗi (do rò rỉ bộ nhớ sập tiến trình), Kubernetes/Docker sẽ lập tức hủy diệt container đó để tái khởi động lại một bản sao mới.
- `/readyz` (Readiness probe): Khảo sát xem dịch vụ đã sẵn sàng tiếp nhận traffic thực tế chưa. Ví dụ: Khi app mới khởi động, nó cần 1 phút để tải file đồ thị lớn từ DB vào RAM. Trong 1 phút đó, `/healthz` trả về 200 (tôi vẫn sống), nhưng `/readyz` trả về 503 (tôi chưa sẵn sàng nhận khách). Bộ cân bằng tải (Load Balancer) sẽ dựa vào `/readyz` để không đẩy traffic vào một service chưa load xong dữ liệu.

## 5. POST 4 request đồng thời. Endpoint handle ổn không? Bottleneck đầu tiên?
- Với cấu hình mã nguồn sử dụng cơ chế xử lý bất đồng bộ `async/await` chạy trên Uvicorn ASGI server, endpoint hoàn toàn xử lý ổn định và mượt mà 4 request gửi lên đồng thời nhờ vào vòng lặp sự kiện (Event Loop). Khi request 1 rảnh tay chờ mạng LLM phản hồi, tiến trình sẽ nhường CPU để xử lý tiếp request 2, 3, 4.
- Bottleneck đầu tiên xuất hiện khi số lượng request đồng thời vượt ngưỡng chịu tải của luồng xử lý hoặc chạm vào giới hạn Rate Limit của tài khoản LLM Provider, dẫn đến lỗi `429 Too Many Requests` trả về từ nhà cung cấp. Cách xử lý là tăng số lượng `--workers` và triển khai hàng đợi (Queue) hoặc Cache tập trung.