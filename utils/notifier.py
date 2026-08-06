#utils/notifier.py

import requests
import os
import smtplib
import pandas as pd
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_line_summary(results, source_name, tw_time, status_col_name='策略狀態'):
    """【單一職責】純粹處理 LINE 的文字摘要發送。不管有沒有股票都要通知狀態。"""
    now_str = tw_time.strftime('%Y-%m-%d %H:%M')
    
    if not results:
        message_text = f"📅 [{source_name}] {now_str}\n今日無符合條件之股票。"
    else:
        report = pd.DataFrame(results)
        report = report.sort_values(by=['觸發策略', '代號'], ascending=[False, True])
        #short_report = report[['代號', '名稱', '收盤', status_col_name]]
        short_report = report[['代號', '名稱', '收盤', '觸發策略','觸發狀態',]]
        message_text = f"📅 [{source_name}] 掃描完成: {now_str}\n=== 精選名單 ===\n\n{short_report.to_string(index=False)}"
    
    # 實際執行 LINE 發送 (依據你的實戰需求暫時註解或啟用)
    send_line_message(message_text)
    print(f"📢 [LINE 訊息已就緒]:\n{message_text}\n")


def send_email_report(file_path):
    """【單一職責】純粹處理 Email 檔案附件發送。只有當實體檔案存在時才啟動。"""
    if not (file_path and os.path.exists(file_path)):
        print("💡 [Email 提示] 無實體檔案產出，跳過 Email 發送流程。")
        return

    SENDER = os.getenv("SENDER_EMAIL")
    RECEIVER = os.getenv("RECIPIENT_EMAIL")
    PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
    
    if SENDER and RECEIVER and PASSWORD:
        print(f"📧 [Email 啟動] 正在發送檔案: {file_path}")
        send_email_with_csv(file_path, RECEIVER, SENDER, PASSWORD)
    else:
        print("⚠️ [Email 錯誤] 缺少環境變數 (SENDER/RECEIVER/PASSWORD)，取消寄送。")

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

def send_email_with_csv(file_path, recipient_email, sender_email, app_password):
    """
    發送包含 CSV 附件的 Email (支援中文檔名安全編碼與自動連線管理)
    """
    # 確保檔案存在
    if not os.path.exists(file_path):
        print(f"❌ 寄送 Email 失敗: 找不到檔案 {file_path}")
        return False

    filename = os.path.basename(file_path)
    
    # 1. 設定郵件標題與內容
    subject = f"📊 股市掃描報告 - {filename}"
    body = "您好，附件為今日的股市掃描結果 CSV 檔案，請查收。"

    # 2. 建立郵件物件
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    # 郵件主旨使用 UTF-8 編碼防止中文亂碼
    msg['Subject'] = Header(subject, 'utf-8').encode()
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # 3. 處理附件檔案
    try:
        with open(file_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        # 將檔案編碼為 Base64
        encoders.encode_base64(part)
        
        # 🌟 修正：使用 Header 處理附件中文檔名，防止收到 noname 或亂碼
        # 移除原先 filename= 後方不必要的空格
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=Header(filename, 'utf-8').encode()
        )
        msg.attach(part)

        # 4. 連線至 Gmail SMTP 伺服器並寄出 (🌟 改用 with 語法自動關閉連線)
        print("🔄 正在連線至 Gmail SMTP 伺服器...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # 啟動安全傳輸
            server.login(sender_email, app_password)
            server.send_message(msg)
        
        print(f"✅ Email 已成功寄送至 {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("❌ 寄送 Email 失敗: 帳號或應用程式密碼 (App Password) 錯誤，請檢查安全性設定。")
        return False
    except Exception as e:
        print(f"❌ 寄送 Email 發生預期外錯誤: {str(e)}")
        return False


def send_email_with_csv_old(file_path, recipient_email, sender_email, app_password):
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
