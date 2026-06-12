# Lab — Evidence-Driven Remediation Engine — Data Pack

This pack contains everything you need to run the lab described in the handout.

## 1. Contents

data-pack/
├── eval/
│   ├── E01.json ... E08.json          (8 evaluation incidents)
│   └── expected.json                  (ground-truth accepted actions)
├── incidents_history.json             (~29 past incidents)
├── topology.json                      (canonical service topology)
├── actions.yaml                       (remediation action catalog)
├── grade.py                           (auto-grader — run after you produce audit.jsonl)
├── features.py                        (Layer 1 — Observability feature extraction)
├── retrieval.py                       (Layer 2 — Semantic RAG & Collaborative voting)
├── decision.py                        (Layer 3 — Expected Value risk analysis & OOD bypass)
├── engine.py                          (Main CLI Orchestrator execution entry-point)
├── audit.jsonl                        (Generated engineering execution audit trail)
└── README.md                          (This runbook documentation file)

## 2. Core Architecture Pipeline

Engine vận hành theo mô hình đường ống xử lý phân tầng nghiêm ngặt nhằm biến đổi các dữ liệu quan trắc hỗn loạn thành các hành động vá lỗi live-mesh mang tính an toàn và tuân thủ chính sách cao:

1. **Layer 1 — `features.py` (Feature Extraction):** Sử dụng cấu trúc cây trực tuyến cố định chiều sâu Drain3 để làm sạch nhiễu tokens động của logs, tính toán sai lệch phân vị dữ liệu $p99$ của traces để khoanh vùng mạng lưới microservices đang bị tổn thương (`affected_services`).
2. **Layer 2 — `retrieval.py` (Precedent Retrieval):** Áp dụng phép chấm điểm lai Hybrid Multi-Metric RAG (50% Ngữ nghĩa Logs qua Vector Embedding `bge-small-en-v1.5`, 30% Chỉ số mạng Traces, 20% Topo ảnh hưởng Jaccard) kết hợp với thuật toán Bỏ phiếu có trọng số kết quả thành/bại dĩ vãng (Outcome-Weighted Voting).
3. **Layer 3 — `decision.py` (Risk-Aware Decision):** Định giá rủi ro kinh tế live-mesh qua mô hình Giá trị kỳ vọng ($EV$). Nếu dính lỗi lạ Ngoài phân phối (OOD < 0.55 similarity), hệ thống ngắt tự động hóa cấu hình, kích hoạt thuật toán duyệt đồ thị Topology ngược dòng mạng tìm nguồn phát dịch sâu nhất, trả về lệnh an toàn tối cao `page_oncall` và triệu hồi mô hình `gemini-2.5-flash` làm Cố vấn chiến lược sinh phác đồ xử lý sự cố trực quan.

---

## 3. Quick Start & Environment Setup

Hệ thống yêu cầu cài đặt môi trường **Python 3.10+**. Thực hiện khởi tạo môi trường ảo và cài đặt các gói thư viện quan trắc hạ tầng phụ thuộc:

```bash
uv venv --python 3.12
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
uv pip install pandas numpy scikit-learn pyyaml sentence-transformers google-genai
```

## 3. Cấu hình Khóa bảo mật AI (Gemini API Key)

Để kích hoạt luồng xử lý khẩn cấp khi gặp sự cố lạ (OOD) và nhận phác đồ tư vấn chiến lược tự động giải trình logs từ mô hình `gemini-2.5-flash`, bạn bắt buộc phải nạp khóa API vào biến môi trường Terminal trước khi khởi chạy Engine.

### Trên Windows PowerShell

```powershell
$env:GEMINI_API_KEY="NHẬP_MÃ_API_KEY_CỦA_BẠN_TẠI_ĐÂY" 
```

### Trên Linux / macOS Terminal

```bash
export GEMINI_API_KEY="NHẬP_MÃ_API_KEY_CỦA_BẠN_TẠI_ĐÂY"
```

---

## 4. Execution Commands & Automation

### Chạy kiểm thử đơn lẻ một sự cố (CLI Contract)

Thực thi phân tích đặc trưng và ra quyết định vá lỗi cho một tệp kịch bản live sự cố cụ thể bằng lệnh:

```bash
python engine.py decide --incident eval/E01.json \
                        --history incidents_history.json \
                        --actions actions.yaml
```

### Chạy tự động hóa hàng loạt toàn bộ 8 file Test (Batch Pipeline)

Sử dụng các lệnh điều phối vòng lặp sau tùy thuộc vào môi trường Shell bạn đang mở để quét toàn bộ 8 ca kiểm thử sự cố và tự động kết xuất nhật ký phục vụ chấm điểm.

#### Môi trường Windows PowerShell

```powershell
1..8 | ForEach-Object {
    python engine.py decide `
        --incident "eval/E0$_.json" `
        --history incidents_history.json `
        --actions actions.yaml
}
```

#### Môi trường Linux / macOS / Git Bash

```bash
for i in {1..8}; do
  python engine.py decide \
      --incident eval/E0${i}.json \
      --history incidents_history.json \
      --actions actions.yaml
done
```

### Chạy công cụ chấm điểm tự động (Auto-Grader)

Sau khi chuỗi lệnh trên chạy xong và tạo ra tệp nhật ký tích lũy `audit.jsonl`, hãy thực thi file chấm điểm của bài Lab để đối chiếu độ chính xác với Ground Truth:

```bash
python grade.py --audit audit.jsonl --expected eval/expected.json
```

---

## 5. Expected Output Format

Tệp kết xuất nhật ký kiểm toán sinh ra tại `audit.jsonl` phải đáp ứng nghiêm ngặt hợp đồng cấu trúc chấm điểm tự động và phục vụ rà soát thủ công:

```json
{
  "incident_id": "E07",
  "selected_action": "page_oncall",
  "params": {
    "team": "platform-sre"
  },
  "confidence": 0.5,
  "evidence": {
    "top_historical_matches": [],
    "derived_affected_services": ["inventory-svc"],
    "ood_flag": true,
    "ev_calculation": {
      "note": "Novel incident pattern detected. Out-of-distribution automated escalation triggered.",
      "topology_analysis": {
        "suspected_root_cause": "inventory-svc",
        "propagation_path": ["inventory-svc"]
      },
      "llm_remediation_advisor": {
        "suggested_action": "restart_pod",
        "suggested_params": {
          "service": "inventory-svc",
          "pod_selector": "all"
        },
        "justification": "The logs indicate Kubernetes API throttling and informer cache sync failures, which a pod restart can resolve by resetting client connections and internal states."
      }
    },
    "extracted_drain_templates": [
      "informer cache sync failed after 60s",
      "Kubernetes API throttled: 429 too many requests"
    ]
  }
}
```

---

## 6. Submission

Khi nộp bài Lab, hãy đảm bảo thư mục gốc của bạn đóng gói đầy đủ cấu trúc tệp sạch như sau:

```text
your-name/
├── engine.py
├── features.py
├── retrieval.py
├── decision.py
├── actions.yaml
├── audit.jsonl
│   └── (Phải chứa đủ 8 dòng JSON tương ứng từ E01 đến E08)
├── FINDINGS.md
│   └── (Báo cáo giải trình 5 câu hỏi cốt lõi của Lab)
└── README.md
    └── (Tài liệu hướng dẫn vận hành này)
```
