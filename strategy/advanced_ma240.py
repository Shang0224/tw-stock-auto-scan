from FinMind.data import DataLoader
import pandas as pd
from datetime import datetime, timedelta
import time

# --- 1. 策略邏輯函數 (具備自主抓資料權力) ---
def st_advanced_ma240_df(df):
    """
    進階策略：年線上下3% + 均線糾結 + 帶量轉強
    """
      
    # 基礎檢查：資料量需足夠計算年線
    if df.empty or len(df) < 240:
        return False, {}

    # 計算技術指標
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA60'] = df['close'].rolling(60).mean()
    df['MA240'] = df['close'].rolling(240).mean()
    
    today = df.iloc[-1]

    # --- 篩選條件 ---
    # 條件 1: 距離年線 3% 以內
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    is_near_ma240 = abs(dist_ratio) <= 0.03
    
    # 條件 2: 均線糾結 (5, 20, 60MA 差距在 5% 內，代表中短期成本一致)
    ma_list = [today['MA5'], today['MA20'], today['MA60']]
    dispersion = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_converged = dispersion < 0.05
    
    # 條件 3: 帶量 (今日量 > 5日均量 1.2倍)
    vol_ma5 = df['Trading_Volume'].rolling(5).mean().iloc[-1]
    is_volume_up = today['Trading_Volume'] > vol_ma5 * 1.2 if vol_ma5 > 0 else False

    # 綜合判斷：只要靠近年線且「糾結」或「帶量」其中之一符合即可視為預備股
    is_hit = is_near_ma240 and (is_converged or is_volume_up)
    
    status = "年線上方整理" if dist_ratio > 0 else "年線下方待突破"
    
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio*100, 2)}%",
        "糾結度": f"{round(dispersion*100, 2)}%",
        "量比": f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x",
        "狀態": status
    }

    print(f"st_advanced_ma240(  df  ) is_hit:{is_hit}   info:{info}")
    
    return is_hit, info



# --- 1. 策略邏輯函數 (具備自主抓資料權力) ---
def st_advanced_ma240(sid, dl, name_map):
    """
    進階策略：年線上下3% + 均線糾結 + 帶量轉強
    """
      
    # 策略決定抓取 500 天資料
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    
    df = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
    
    # 基礎檢查：資料量需足夠計算年線
    if df.empty or len(df) < 240:
        return False, {}

    # 計算技術指標
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA60'] = df['close'].rolling(60).mean()
    df['MA240'] = df['close'].rolling(240).mean()
    
    today = df.iloc[-1]
    s_name = name_map.get(sid, sid)

    # --- 篩選條件 ---
    # 條件 1: 距離年線 3% 以內
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    is_near_ma240 = abs(dist_ratio) <= 0.03
    
    # 條件 2: 均線糾結 (5, 20, 60MA 差距在 5% 內，代表中短期成本一致)
    ma_list = [today['MA5'], today['MA20'], today['MA60']]
    dispersion = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_converged = dispersion < 0.05
    
    # 條件 3: 帶量 (今日量 > 5日均量 1.2倍)
    vol_ma5 = df['Trading_Volume'].rolling(5).mean().iloc[-1]
    is_volume_up = today['Trading_Volume'] > vol_ma5 * 1.2 if vol_ma5 > 0 else False

    # 綜合判斷：只要靠近年線且「糾結」或「帶量」其中之一符合即可視為預備股
    is_hit = is_near_ma240 and (is_converged or is_volume_up)
    
    status = "年線上方整理" if dist_ratio > 0 else "年線下方待突破"
    
    info = {
        "代號": sid,
        "名稱": s_name,
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio*100, 2)}%",
        "糾結度": f"{round(dispersion*100, 2)}%",
        "量比": f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x",
        "狀態": status
    }

    print(f"st_advanced_ma240 is_hit:{is_hit}   info:{info}")
    
    return is_hit, info
