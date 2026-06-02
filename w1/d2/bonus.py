import argparse
import sys
import pandas as pd
from datetime import datetime, timedelta
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from drain3.masking import RegexMaskingInstruction

def extract_timestamp(line):
    """
    Tự động nhận diện thời gian từ nhiều định dạng log chuẩn (HDFS, BGL, Spark).
    """
    parts = line.split()
    if len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) == 10:
        try: return datetime.fromtimestamp(int(parts[1]))
        except ValueError: pass
    if len(parts) >= 2:
        try:
            time_str = f"{parts[0]} {parts[1]}"
            return datetime.strptime(time_str, '%y%m%d %H%M%S')
        except ValueError: pass
        try:
            time_str = f"{parts[0]} {parts[1].split(',')[0]}"
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError: pass
    return None

def main(logfile):
    print(f"🚀 Đang phân tích file log: {logfile}...\n")
    
    # 1. KHỞI TẠO DRAIN3 & THÊM LUẬT MASKING CHO DOCKER
    config = TemplateMinerConfig()
    config.drain_sim_th = 0.5
    
    # Tuyệt chiêu xử lý Docker: Che toàn bộ chuỗi ký tự a-f, 0-9 có độ dài đúng 64 ký tự
    docker_hash_mask = RegexMaskingInstruction(r'[a-f0-9]{64}', '<DOCKER_HASH>')
    config.masking_instructions.append(docker_hash_mask)
    
    miner = TemplateMiner(config=config)
    
    log_data = []
    
    # Cài đặt mốc thời gian giả lập ban đầu cho log không có timestamp
    simulated_time = datetime(2026, 1, 1, 12, 0, 0)
    
    # 2. Đọc file và Parse
    try:
        with open(logfile, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                timestamp = extract_timestamp(line)
                
                # --- GIẢ LẬP THỜI GIAN NẾU KHÔNG TÌM THẤY ---
                if not timestamp:
                    timestamp = simulated_time
                    simulated_time += timedelta(seconds=1) # Mỗi dòng cách nhau 1 giây
                
                result = miner.add_log_message(line)
                
                log_data.append({
                    'timestamp': timestamp,
                    'template_id': f"T-{result['cluster_id']:03d}",
                    'template': result['template_mined']
                })
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file: {logfile}")
        sys.exit(1)

    df = pd.DataFrame(log_data)
    df_time = df.dropna(subset=['timestamp']).copy()
    
    total_lines = len(df)
    unique_templates = df['template_id'].nunique()
    
    print("=" * 50)
    print("📊 BÁO CÁO TỔNG QUAN")
    print("=" * 50)
    print(f"Tổng số dòng log: {total_lines:,}")
    print(f"Số lượng Template (Unique): {unique_templates}")
    
    print("\n🏆 TOP 5 TEMPLATES XUẤT HIỆN NHIỀU NHẤT:")
    top_5 = df['template_id'].value_counts().head(5)
    for t_id, count in top_5.items():
        pct = (count / total_lines) * 100
        t_content = df[df['template_id'] == t_id]['template'].iloc[0]
        print(f" - {t_id}: {count:,} lần ({pct:.1f}%) | {t_content[:70]}...")

    if df_time.empty:
        print("\n⚠️ Không thể parse thời gian từ file này.")
        return

    # Tính toán mốc phân định: Do thời gian giả lập khá ngắn, ta dùng 5 phút cuối làm "recent" thay vì 1 giờ
    max_time = df_time['timestamp'].max()
    cutoff_time = max_time - timedelta(minutes=5)
    
    df_past = df_time[df_time['timestamp'] < cutoff_time]
    df_recent = df_time[df_time['timestamp'] >= cutoff_time]
    
    past_templates = set(df_past['template_id'].unique())
    recent_templates = set(df_recent['template_id'].unique())
    
    print("\n🚨 CẢNH BÁO: NEW TEMPLATES (PHẦN CUỐI FILE):")
    new_templates = recent_templates - past_templates
    if new_templates:
        for t_id in new_templates:
            count = len(df_recent[df_recent['template_id'] == t_id])
            t_content = df_recent[df_recent['template_id'] == t_id]['template'].iloc[0]
            print(f" [NEW] {t_id} (Xuất hiện {count} lần): {t_content[:70]}...")
    else:
        print(" ✅ Không phát hiện Template mới.")

    print("\n📈 CẢNH BÁO: SPIKES - TĂNG ĐỘT BIẾN:")
    minutes_in_past = max(1.0, (cutoff_time - df_time['timestamp'].min()).total_seconds() / 60)
    
    found_spike = False
    for t_id in recent_templates:
        if t_id in new_templates: continue 
            
        recent_count = len(df_recent[df_recent['template_id'] == t_id])
        past_count = len(df_past[df_past['template_id'] == t_id])
        
        avg_past_per_min = past_count / minutes_in_past
        
        # Tiêu chí Spike mô phỏng: Lớn hơn gấp 3 lần trung bình quá khứ
        if recent_count > 5 and recent_count > (avg_past_per_min * 3):
            print(f" [SPIKE] {t_id}: {recent_count} lần (Trung bình cũ: {avg_past_per_min:.1f} lần/phút)")
            found_spike = True
            
    if not found_spike:
        print(" ✅ Hệ thống ổn định, không có Template tăng đột biến.")
    print("=" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mini Log Analyzer - AIOps Assignment")
    parser.add_argument("logfile", help="Đường dẫn tới file log cần phân tích")
    args = parser.parse_args()
    
    main(args.logfile)