# utils/storage.py
import os
import paramiko

import os
import posixpath
import paramiko

def ensure_remote_dir(sftp, remote_dir):
    """
    遞迴確保 SFTP 遠端多層目錄存在 (相當於 mkdir -p)
    """
    dirs = []
    path = remote_dir
    while path and path != '/':
        dirs.append(path)
        path = posixpath.dirname(path)
    
    # 從最上層父目錄開始往下檢查並建立
    while dirs:
        dir_to_check = dirs.pop()
        try:
            sftp.stat(dir_to_check)
        except IOError:
            print(f"📁 遠端目錄不存在，自動建立：{dir_to_check}")
            sftp.mkdir(dir_to_check)

def upload_to_nas(host, port, username, password, local_path, remote_path):
    """
    透過 Tailscale 內網 IP 上傳檔案至 NAS。
    """
    print("upload_to_nas\n")
    
    # 1. 基礎檢查：參數與本地檔案是否存在    
    if not all([host, port, username, password]):
        raise ValueError("❌ 錯誤：NAS 連線資訊不完整，請檢查環境變數 (Secrets)。")
    
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"❌ 錯誤：本地待上傳檔案不存在：{local_path}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sftp = None

    try:
        print(f"🔗 正在嘗試連線至 Tailscale 節點: {host}:{port}...")
        
        # 2. 建立 SSH 連線
        ssh.connect(
            hostname=host, 
            port=int(port), 
            username=username, 
            password=password,
            timeout=30,
            banner_timeout=30
        )

        # 3. 開啟 SFTP
        sftp = ssh.open_sftp()
       
        # 使用 posixpath 確保跨平台相容 Linux NAS 路徑
        remote_dir = posixpath.dirname(remote_path)
        print(f"遠端目標路徑：{remote_path} | 遠端目錄：{remote_dir}")

        # 4. 確保遠端多層目錄存在 (自動建立不存在的父資料夾)
        if remote_dir:
            ensure_remote_dir(sftp, remote_dir)

        # 5. 執行上傳
        print(f"🚀 開始上傳：{os.path.basename(local_path)} -> {remote_path}")
        sftp.put(local_path, remote_path)
        print("✅ 上傳成功！")

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
        # 6. 安全關閉連線
        if sftp:
            try:
                sftp.close()
            except Exception:
                pass
        ssh.close()
        print("🔌 已斷開 SSH 連線。")


def upload_to_nas_old(host, port, username, password, local_path, remote_path):
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
       
        remote_dir = os.path.dirname(remote_path)
        print(f"remote_path：{remote_path}  remote_dir: {remote_dir}\n")

        # 5. 確保遠端目錄存在
        try:
            sftp.stat(remote_dir)
        except IOError:
            # 🌟 若遠端資料夾不存在，自動幫忙建立目錄
            sftp.mkdir(remote_dir)
            print(f"sftp.mkdir(remote_dir) : {remote_dir}\n")
        
        
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
