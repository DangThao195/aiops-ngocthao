# Phase 1: End-to-End Data Layer Architecture
**Use Case:** Anomaly Detection trên Payment Service (Phát hiện giao dịch/hệ thống thanh toán bất thường theo thời gian thực).

### Sơ đồ Kiến trúc (Mermaid)

```mermaid
flowchart LR
    %% Định nghĩa các node với cú pháp an toàn (dùng ngoặc kép và thẻ <br>)
    subgraph S1 ["1. Service Layer"]
        P["Payment Service<br>(Java/Go)"]
        SDK["OpenTelemetry SDK"]
        P --> SDK
    end

    subgraph S2 ["2. Collection"]
        Col["OTel Collector<br>(DaemonSet)"]
        SDK -->|gRPC/HTTP| Col
    end

    subgraph S3 ["3. Transport"]
        Kafka[("Apache Kafka<br>Message Queue")]
        Col -->|Produce| Kafka
    end

    subgraph S4 ["4. Processing"]
        Flink["Apache Flink<br>(Stream Processing)"]
        Kafka -->|Consume| Flink
    end

    subgraph S5 ["5. Storage"]
        VM[("VictoriaMetrics<br>Time-series DB")]
        S3[("AWS S3<br>Cold Storage/Parquet")]
        Flink -->|Hot Data| VM
        Flink -->|Cold Data / Features| S3
    end

    subgraph S6 ["6. Query / AI Layer"]
        Grafana["Grafana Dashboard"]
        ML["Anomaly Detection<br>ML Model"]
        VM -->|PromQL| Grafana
        VM -->|Real-time Features| ML
        S3 -->|Batch Training| ML
    end

    %% Đổ màu cho đẹp
    style P fill:#f9f,stroke:#333,stroke-width:2px
    style Kafka fill:#f96,stroke:#333,stroke-width:2px
    style Flink fill:#6cf,stroke:#333,stroke-width:2px
    style VM fill:#ff9,stroke:#333,stroke-width:2px
    style ML fill:#9f9,stroke:#333,stroke-width:2px