import pandas as pd
import os
import requests
import smtplib
import time
import yfinance as yf

from datetime import datetime, timedelta, timezone
from FinMind.data import DataLoader
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import paramiko


def yf_fetch_all_stocks(stock_ids, start_date, end_date):
    """
    將原有的 FinMind 邏輯改為使用 yfinance 取得台股資料
    
    :param stock_ids: list, 例如 ['2330.TW', '2454.TW'] 或 ['2330', '2454']
    :param start_date: str, 格式 'YYYY-MM-DD'
    :param end_date: str, 格式 'YYYY-MM-DD'
    """
    all_data = []
    
    print(f"📡 正在透過 yfinance 抓取 {len(stock_ids)} 檔股票...")
  
    for sid in stock_ids:
        # 自動補齊台股後綴 (若使用者只輸入 2330)
        ticker_id = f"{sid}.TW" if "." not in str(sid) else sid
        print(f"yf_fetch_all_stocks ticker_id : {ticker_id} \n")
        
        try:
            # yfinance 下載資料
            # auto_adjust=True 會自動處理除權息調整價
            
            print(f"yf.download ticker_id:{ticker_id}  start:{start_date}  end:{end_date}\n")
            df = yf.download(ticker_id, start=start_date, end=end_date, progress=False, multi_level_index=False)
            
            if not df.empty:
                
                df.index = df.index.strftime('%Y-%m-%d') # 先把 Index 轉成字串
                print(f"df.loc[-1] : {df.loc[-1]}\n")  # 此時 loc[end_date] 還是有效的！
                
                if end_date in df.index:
                    print(f"--- {end_date} 的完整資料 ---")
                    print(df.loc[end_date])  # 此時 loc[end_date] 還是有效的！
                else:
                    print(f"找不到 {end_date}")
                
                # 重整格式：yfinance 預設 index 是 Date，轉換成欄位方便合併
                df = df.reset_index()          
                
                # 加入股票代碼欄位以便後續辨識
                df['stock_id'] = sid
                
                # 統一欄位名稱為小寫 (符合原本 FinMind 習慣，自由選用)
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                df.rename(columns={'volume': 'Trading_Volume'}, inplace=True)
                df.rename(columns={'high': 'max'}, inplace=True)
                df.rename(columns={'low': 'min'}, inplace=True)
        
                all_data.append(df)
            
            # 延遲避免請求過於頻繁
            time.sleep(2)
            
        except Exception as e:
            print(f"⚠️ 抓取 {ticker_id} 失敗: {e}")
            continue
            
    if not all_data:
        print("❌ 未抓取到任何資料")
        return pd.DataFrame()
        
    # 合併所有資料並重置 index
    final_df = pd.concat(all_data, ignore_index=True)
    return final_df


def upload_to_nas(host, port, username, password, local_path, remote_path):
    """
    透過 Tailscale 內網 IP 上傳檔案至 NAS。
    """
    # 1. 基礎檢查：確保必要參數都有值
    if not all([host, username, password]):
        raise ValueError("❌ 錯誤：NAS 連線資訊不完整，請檢查環境變數 (Secrets)。")

    ssh = paramiko.SSHClient()
    
    # 2. 自動接受 SSH 指紋 (在 GitHub Actions 這種乾淨環境必備)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔗 正在嘗試連線至 Tailscale 節點: {host}:{port}...")
        
        # 3. 建立連線
        # timeout: 等待 TCP 連線建立的時間
        # banner_timeout: 等待 SSH 協定握手的時間
        ssh.connect(
            hostname=host, 
            port=int(port), 
            username=username, 
            password=password,
            timeout=30,
            banner_timeout=30
        )

        # 4. 開啟 SFTP
        sftp = ssh.open_sftp()

        # 5. 確保遠端目錄存在
        remote_dir = os.path.dirname(remote_path)
        #print(f"remote_path：{remote_path}  remote_dir: {remote_dir}")
        
        try:
            sftp.chdir(remote_dir)
        except IOError:
            # 如果目錄不存在，可以選擇直接報錯或自動建立
            # 這裡我們選擇拋出異常，確保你的路徑設定是正確的
            raise FileNotFoundError(f"❌ 遠端目錄不存在：{remote_dir}")

        # 6. 執行上傳
        print(f"🚀 開始上傳：{os.path.basename(local_path)} -> {remote_path}")
        sftp.put(local_path, remote_path)
        print(f"✅ 上傳成功！")

    except paramiko.AuthenticationException:
        print("❌ 認證失敗：請檢查 NAS 的帳號或密碼是否正確。")
        raise
    except paramiko.SSHException as e:
        print(f"❌ SSH 協定錯誤：{e}")
        raise
    except Exception as e:
        print(f"❌ 發生非預期錯誤: {e}")
        raise
    finally:
        # 7. 確保不論成功失敗都會關閉連線
        if 'sftp' in locals():
            sftp.close()
        ssh.close()
        print("🔌 已斷開 SSH 連線。")

def send_email_with_csv(file_path, recipient_email, sender_email, app_password):
    # 1. 設定郵件標題與內容
    subject = f"📊 股市掃描報告 - {os.path.basename(file_path)}"
    body = "您好，附件為今日的股市掃描結果 CSV 檔案，請查收。"

    # 2. 建立郵件物件
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # 3. 處理附件檔案
    try:
        with open(file_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        # 將檔案編碼為 Base64
        encoders.encode_base64(part)
        
        # 設定附件標頭
        filename = os.path.basename(file_path)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {filename}",
        )
        msg.attach(part)

        # 4. 連線至 Gmail SMTP 伺服器並寄出
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls() # 啟動安全傳輸
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email 已成功寄送至 {recipient_email}")
        
    except Exception as e:
        print(f"❌ 寄送 Email 失敗: {str(e)}")

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

def fm_fetch_all_stocks(dl, stock_ids, start_date, end_date):
    all_data = []
    
    print(f"串聯抓取 {len(stock_ids)} 檔股票...")
    
    for sid in stock_ids:
        try:
            # 逐一抓取
            df = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
            
            if df is not None and not df.empty:
                all_data.append(df)
            
            # 重要：如果您沒有 Token，建議加上微小延遲避免被封鎖
            time.sleep(0.5) 
            
        except Exception as e:
            print(f"⚠️ 抓取 {sid} 失敗: {e}")
            continue
            
    if not all_data:
        return pd.DataFrame()
        
    # 一次性垂直合併所有 Dataframe
    return pd.concat(all_data, ignore_index=True)

def smart_read_csv(file_path):
    # 測試清單：UTF-8 (現代標準), Big5 (台灣常見), UTF-8-SIG (Excel 專用)
    encodings = ['utf-8', 'big5', 'utf-8-sig', 'cp950']
    
    for enc in encodings:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            print(f"✅ 成功使用 {enc} 編碼讀取檔案！")
            return df
        except UnicodeDecodeError:
            continue
    
    print("❌ 找不到匹配的編碼，請檢查檔案格式。")
    return None

def send_line_message(message):
    """透過 LINE Messaging API 發送訊息"""
    token = os.getenv("LINE_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    #print(f"USER ID : {user_id}\nMessage {message}")
    
    if not token or not user_id:
        print("錯誤：找不到 LINE 的設定資訊 (Secrets)")
        return

    url = "https://api.line.me/v2/bot/message/push"       
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }

    #print(f"USER ID : {user_id}\nMessage {message}")
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        print("LINE 報告發送成功！")
    else:
        print(f"發送失敗，狀態碼：{res.status_code}, 內容：{res.text}")
