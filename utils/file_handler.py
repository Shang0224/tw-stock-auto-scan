# utils/file_handler.py
import os
import pandas as pd
from FinMind.data import DataLoader            # 🟢 修正 1：補上漏掉的 FinMind 匯入
from utils.notifier import send_line_message 
from utils.storage import upload_to_nas  

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
