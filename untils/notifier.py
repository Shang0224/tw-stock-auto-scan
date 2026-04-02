import pandas as pd
import os
import requests
import smtplib
import time

from datetime import datetime, timedelta, timezone
from FinMind.data import DataLoader
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import paramiko


def upload_to_nas(host, port, username, password, local_path, remote_path):
    """
    使用 paramiko SSHClient 上傳檔案，並在連線失敗或目錄不存在時拋出異常。
    """
    ssh = paramiko.SSHClient()
    
    # 自動接受未知的 SSH key (第一次連線 NAS 時必需)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"正在連線至 {host}:{port}...")
        # 建立連線，增加 timeout 防止 GitHub Actions 卡死
        ssh.connect(
            hostname=host, 
            port=port, 
            username=username, 
            password=password,
            timeout=30,           # 建立 TCP 連線的超時
            banner_timeout=30     # 等待 SSH 橫幅回傳的超時
        )

        # 開啟 SFTP 通道
        sftp = ssh.open_sftp()

        # 檢查遠端目錄是否存在
        remote_dir = os.path.dirname(remote_path)
        try:
            sftp.chdir(remote_dir)
        except IOError:
            raise FileNotFoundError(f"❌ 遠端目錄不存在：{remote_dir}")

        # 執行上傳
        print(f"正在上傳 {local_path} -> {remote_path}")
        sftp.put(local_path, remote_path)
        print(f"✅ 檔案已成功上傳至 NAS！")

    except paramiko.ssh_exception.NoValidConnectionsError:
        print("❌ 無法建立連線：請確認 NAS 的 IP 與 Port 是否正確，且防火牆已開啟。")
        raise
    except paramiko.AuthenticationException:
        print("❌ 認證失敗：請檢查 NAS 的帳號或密碼。")
        raise
    except Exception as e:
        print(f"❌ 上傳過程中發生錯誤: {e}")
        raise
    finally:
        # 確保資源釋放
        if 'sftp' in locals():
            sftp.close()
        ssh.close()

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

def fetch_all_stocks(dl, stock_ids, start_date, end_date):
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

    print(f"USER ID : {user_id}\nMessage {message}")
    
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

    print(f"USER ID : {user_id}\nMessage {message}")
    
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        print("LINE 報告發送成功！")
    else:
        print(f"發送失敗，狀態碼：{res.status_code}, 內容：{res.text}")
