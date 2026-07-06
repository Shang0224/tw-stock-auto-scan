# utils/storage.py
import os
import paramiko


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
        print("🔌 已斷開 
