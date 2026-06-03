# Phase 1: End-to-End Data Layer Architecture
**Use Case:** Anomaly Detection trên Payment Service (Phát hiện giao dịch/hệ thống thanh toán bất thường theo thời gian thực).

### Sơ đồ Kiến trúc (Mermaid)

```mermaid
flowchart LR
    %% Định nghĩa các node
    subgraph "1. Service Layer"
        P[Payment Service\n(Java/Go)]
        SDK[OpenTelemetry SDK]
        P --> SDK
    end

    subgraph "2. Collection"
        Col[OTel Collector\n(DaemonSet)]
        SDK -->|gRPC/HTTP| Col
    end

    subgraph "3. Transport"
        Kafka[(Apache Kafka\nMessage Queue)]
        Col -->|Produce| Kafka
    end

    subgraph "4. Processing"
        Flink[Apache Flink\n(Stream Processing)]
        Kafka -->|Consume| Flink
    end

    subgraph "5. Storage"
        VM[(VictoriaMetrics\nTime-series DB)]
        S3[(AWS S3\nCold Storage/Parquet)]
        Flink -->|Hot Data| VM
        Flink -->|Cold Data / Features| S3
    end

    subgraph "6. Query / AI Layer"
        Grafana[Grafana Dashboard]
        ML[Anomaly Detection\nML Model]
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