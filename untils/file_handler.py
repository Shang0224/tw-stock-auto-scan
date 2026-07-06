# utils/file_handler.py
import os
import pandas as pd
from utils.notifier import send_line_message # 🟢 跨模組呼叫：處理完順便叫 notifier 發 LINE

def send_report(results, source_name, tw_time, status_col_name='觸發策略'):
    """【職責】處理結果、儲存本地 CSV、並呼叫通知模組發送 LINE"""
    now_str = tw_time.strftime('%Y-%m-%d %H:%M')
    current_time = tw_time.strftime("%Y%m%d_%H%M")
    file_name = f'data/{source_name}/{source_name}_scan_report_{current_time}.csv'

    if results:
        report = pd.DataFrame(results)
        report = report.sort_values(by=['觸發策略', '代號'], ascending=[False, True])
        short_report = report[['代號', '名稱', '收盤', status_col_name]]
        message_text = f"📅 [{source_name}] 掃描完成: {now_str}\n=== 精選名單 ===\n\n{short_report.to_string(index=False)}"
        
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        report.to_csv(file_name, index=False, encoding='utf-8-sig')
    else:
        message_text = f"📅 [{source_name}] {now_str}\n今日無符合條件之股票。"

    # 🟢 漂亮的跨模組串接
    send_line_message(message_text)
    return file_name

def cleanup_local_file(file_path):
    """
    清理本地暫存檔，確保環境整潔。
    """
    print(f"cleanup_local_file({file_path})")
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"🧹 成功刪除本地暫存檔：{file_path}")
        except Exception as e:
            print(f"⚠️ 無法刪除檔案 {file_path}，錯誤原因：{e}")
    else:
        print(f"ℹ️ 檔案不存在，無需清理：{file_path}")

def parse_stock_ids(files_env):
    """解析 CSV 檔案取得去重後的股票代號"""
    files = [f.strip() for f in files_env.split(',')]
    stock_ids = []
    for file in files:
        try:
            df = pd.read_csv(file, encoding='big5')
            stock_ids.extend(df['代號'].astype(str).tolist())
            print(f"✅ 讀取成功: {file}")
        except Exception as e:
            print(f"❌ 讀取 {file} 失敗: {e}")
    return list(set(stock_ids))

def get_stock_name_dict():
    """獲取全市場基本資訊名稱字典"""
    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")    
    dl = DataLoader(token=finmindtoken)
    df_info = dl.taiwan_stock_info()
    return dict(zip(df_info['stock_id'], df_info['stock_name'])), dl



