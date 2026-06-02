import argparse
import sys
import pandas as pd
from datetime import datetime, timedelta
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

def extract_timestamp(line):
    parts = line.split()
    
    if len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) == 10:
        try:
            return datetime.fromtimestamp(int(parts[1]))
        except ValueError:
            pass

    if len(parts) >= 2:
        try:
            time_str = f"{parts[0]} {parts[1]}"
            return datetime.strptime(time_str, '%y%m%d %H%M%S')
        except ValueError:
            pass

        try:
            time_str = f"{parts[0]} {parts[1].split(',')[0]}"
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
            
    return None

def main(logfile):
    print(f"Đang phân tích file log: {logfile}...\n")

    config = TemplateMinerConfig()
    config.drain_sim_th = 0.5
    miner = TemplateMiner(config=config)
    
    log_data = []

    try:
        with open(logfile, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                timestamp = extract_timestamp(line)
                result = miner.add_log_message(line)
                
                log_data.append({
                    'timestamp': timestamp,
                    'template_id': f"T-{result['cluster_id']:03d}",
                    'template': result['template_mined']
                })
    except FileNotFoundError:
        print(f"Không tìm thấy file: {logfile}")
        sys.exit(1)

    df = pd.DataFrame(log_data)

    df_time = df.dropna(subset=['timestamp']).copy()

    total_lines = len(df)
    unique_templates = df['template_id'].nunique()
    
    print("=" * 50)
    print("BÁO CÁO TỔNG QUAN")
    print("=" * 50)
    print(f"Tổng số dòng log: {total_lines:,}")
    print(f"Số lượng Template (Unique): {unique_templates}")

    print("\nTOP 5 TEMPLATES XUẤT HIỆN NHIỀU NHẤT:")
    top_5 = df['template_id'].value_counts().head(5)
    for t_id, count in top_5.items():
        pct = (count / total_lines) * 100

        t_content = df[df['template_id'] == t_id]['template'].iloc[0]
        print(f" - {t_id}: {count:,} lần ({pct:.1f}%) | {t_content[:70]}...")

    if df_time.empty:
        print("\nKhông thể parse thời gian từ file này. Bỏ qua phân tích Spike/New Template.")
        return

    max_time = df_time['timestamp'].max()
    cutoff_time = max_time - timedelta(hours=1)
    
    df_past = df_time[df_time['timestamp'] < cutoff_time]
    df_recent = df_time[df_time['timestamp'] >= cutoff_time]
    
    past_templates = set(df_past['template_id'].unique())
    recent_templates = set(df_recent['template_id'].unique())

    print("\nCẢNH BÁO: NEW TEMPLATES (1 GIỜ GẦN NHẤT):")
    new_templates = recent_templates - past_templates
    if new_templates:
        for t_id in new_templates:
            count = len(df_recent[df_recent['template_id'] == t_id])
            t_content = df_recent[df_recent['template_id'] == t_id]['template'].iloc[0]
            print(f" [NEW] {t_id} (Xuất hiện {count} lần): {t_content[:70]}...")
    else:
        print(" Không phát hiện Template mới.")

    print("\nCẢNH BÁO: SPIKES - TĂNG ĐỘT BIẾN (1 GIỜ GẦN NHẤT):")
    hours_in_past = max(1.0, (cutoff_time - df_time['timestamp'].min()).total_seconds() / 3600)
    
    found_spike = False
    for t_id in recent_templates:
        if t_id in new_templates: continue 
            
        recent_count = len(df_recent[df_recent['template_id'] == t_id])
        past_count = len(df_past[df_past['template_id'] == t_id])
        
        avg_past_per_hour = past_count / hours_in_past
        
        if recent_count > 5 and recent_count > (avg_past_per_hour * 3):
            print(f" [SPIKE] {t_id}: {recent_count} lần (Trung bình cũ: {avg_past_per_hour:.1f} lần/giờ)")
            found_spike = True
            
    if not found_spike:
        print(" Hệ thống ổn định, không có Template tăng đột biến.")
    print("=" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mini Log Analyzer - AIOps Assignment")
    parser.add_argument("logfile", help="Đường dẫn tới file log cần phân tích")
    args = parser.parse_args()
    
    main(args.logfile)

'''
Dataset HDFS: Chỉ sinh ra 21 templates unique.
Dataset BGL: Sinh ra tới 151 templates unique (gấp hơn 7 lần so với HDFS).

Giải Thích 
1. HDFS (Hadoop Distributed File System) - Hệ thống phần mềm đơn nhiệm
Bản chất: HDFS là một phần mềm hệ thống tập tin phân tán. Nhiệm vụ cốt lõi của nó chỉ xoay quanh một vài hành động cụ thể: chia nhỏ file, gửi block dữ liệu, nhận block dữ liệu, xóa block, và kiểm tra sức khỏe của các node.
Hệ quả đối với Log: Vì tính chất công việc lặp đi lặp lại rất quy chuẩn, các dòng log sinh ra có sự đồng nhất cao về mặt từ vựng và cấu trúc (ví dụ: Receiving block..., Deleting block...). Do đó, thuật toán Drain3 dễ dàng gom 2,000 dòng log này lại thành một nhóm nhỏ gọn chỉ gồm 21 khuôn mẫu.

2. BGL (Blue Gene/L) - Siêu máy tính phần cứng phức tạp
Bản chất: Blue Gene/L là hệ thống siêu máy tính (Supercomputer) do IBM sản xuất, bao gồm hàng chục ngàn linh kiện: vi xử lý (CPU), chip nhớ (Memory), bảng mạch nội bộ (Node cards), hệ thống mạng lưới (Switch/Router), cảm biến nhiệt độ, và nguồn điện.
Hệ quả đối với Log: Log của BGL là sự pha trộn hỗn mang của cả phần cứng lẫn phần mềm. Một dòng log có thể là thông báo lỗi của hệ điều hành Linux, dòng tiếp theo lại là cảnh báo quá nhiệt từ một con chip, và dòng khác nữa là lỗi cáp quang rớt mạng. Sự đa dạng cực lớn về thành phần hệ thống dẫn đến từ vựng phong phú, cấu trúc câu phức tạp và rất nhiều mã định danh phần cứng khác nhau. Đó là lý do Drain3 phải chẻ nhỏ tập dữ liệu ra thành 151 templates để đảm bảo không bị lẫn lộn giữa lỗi nguồn điện và lỗi phần mềm.'''