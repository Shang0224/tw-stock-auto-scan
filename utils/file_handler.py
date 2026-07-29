# utils/file_handler.py
import os
import pandas as pd
from FinMind.data import DataLoader            # 🟢 修正 1：補上漏掉的 FinMind 匯入
from utils.notifier import send_line_message 
from utils.storage import upload_to_nas  

def save_multi_day_report(collected_results, source_name, tw_time):
    """
    將多日/多組掃描結果格式化寫入同一個 CSV 檔。
    每一天的結果用雙空行格開，並把日期獨立輸出成一行橫線。
    
    :param collected_results: dict, 結構為 {'2026-04-01': [dict, dict], '2026-04-02': [...]}
    :param source_name: str, 來源名稱 (例如 'yf_test')
    :param tw_time: datetime, 當前時間物件 (用於產出檔名時間戳)
    :return: str, 產出的本地 CSV 檔案路徑
    """
    import os
    import pandas as pd
    
    # 1. 沿用你原本的命名與目錄建立邏輯
    current_time = tw_time.strftime("%Y%m%d_%H%M")
    os.makedirs(f"data/{source_name}", exist_ok=True)
    csv_path = f"data/{source_name}/{source_name}_scan_report_{current_time}.csv"
    
    # 2. 開始手動格式化寫入
    with open(csv_path, 'w', encoding='utf-8-sig') as f:
        is_first_day = True
        
        # 確保日期由舊到新排序
        for date_key, day_list in sorted(collected_results.items()):
            if not day_list: # 如果當天沒資料就跳過
                continue
                
            # 每一天中間隔開雙空行
            #if not is_first_day:
            #    f.write("\n")
            
            # 🌟 獨立輸出一行橫線與日期
            #f.write(f"====,=====,==== {date_key} ===========================\n")

            # 將當天的結果寫入 CSV
            # 💡 關鍵：只有第一天 (is_first_day 為 True) 時輸出欄位名稱，後續日期寫入時設為 False
            day_df = pd.DataFrame(day_list)
            day_df.to_csv(f, index=False, header=is_first_day)

            #除了第一次執行is_first_day為true外, 其他為false
            is_first_day = False 
            
    return csv_path

def save_scan_report(results, source_name, tw_time):
    """【職責】只負責處理 DataFrame 數據並儲存本地 CSV，回傳檔案路徑"""
    if not results:
        return None
        
    current_time = tw_time.strftime("%Y%m%d_%H%M")
    file_name = f'data/{source_name}/{source_name}_scan_report_{current_time}.csv'
    
    report = pd.DataFrame(results)
    report = report.sort_values(by=['觸發策略', '代號'], ascending=[False, True])
    
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    report.to_csv(file_name, index=False, encoding='utf-8-sig')
    
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

def archive_and_cleanup(local_file_path, remote_path):
    """【流程組合】負責高階的 備份 + 清理 聯動流程 (遠端路徑由外部決定)"""
    if not local_file_path or not os.path.exists(local_file_path):
        print("ℹ️ 今日無產出報表檔案，無需上傳 NAS。")
        return

    try:
        # 1. 先嘗試上傳 (遠端路徑完全聽從外部指示)
        upload_to_nas(
            host=os.getenv("NAS_VPN_IP"),
            port=int(os.getenv("NAS_SFTP_PORT")),
            username=os.getenv("NAS_ACCOUNT"),
            password=os.getenv("NAS_PASSWORD"),
            local_path=local_file_path,
            remote_path=remote_path  # 👈 直接代入傳進來的完整路徑
        )
        # 2. 上傳成功，才安全地刪除本地檔案
        cleanup_local_file(local_file_path)
        
    except Exception as e:
        print(f"❌ [備份失敗] 網路或 NAS 異常，保留本地檔案以供檢查。錯誤: {e}")


def archive_and_cleanup_old(local_file_path, source_name, tw_time):
    """【流程組合】負責高階的 備份 + 清理 聯動流程"""
    # 🟢 優化 2：如果 local_file_path 是 None (代表今天沒股票、沒生檔案)
    if not local_file_path or not os.path.exists(local_file_path):
        print("ℹ️ 今日無產出報表檔案，無需上傳 NAS。")
        return

    current_time = tw_time.strftime("%Y%m%d_%H%M")
    remote_filename = f"{source_name}_scan_report_{current_time}.csv"
    
    try:
        # 1. 先嘗試上傳
        upload_to_nas(
            host=os.getenv("NAS_VPN_IP"),
            port=int(os.getenv("NAS_SFTP_PORT")),
            username=os.getenv("NAS_ACCOUNT"),
            password=os.getenv("NAS_PASSWORD"),
            local_path=local_file_path,
            remote_path=f"{os.getenv('NAS_SFTP_PATH')}/{source_name}/{remote_filename}"
        )
        # 2. 上傳成功，才安全地刪除本地檔案
        cleanup_local_file(local_file_path)
        
    except Exception as e:
        print(f"❌ [備份失敗] 網路或 NAS 異常，保留本地檔案以供檢查。錯誤: {e}")


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
        
        #--------------------line 超過次數暫停-----------------------------------------------------------
        #send_line_message(message_text)
        return file_name  # 有產出檔案，回傳路徑
    else:
        message_text = f"📅 [{source_name}] {now_str}\n今日無符合條件之股票。"
        #--------------------line 超過次數暫停--------------------------------------------------------------
        #send_line_message(message_text)
        return None  # 🟢 優化 3：明確回傳 None，讓後續 archive 知道今天不用上傳


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
