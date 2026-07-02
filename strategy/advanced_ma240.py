from FinMind.data import DataLoader
import pandas as pd
from datetime import datetime, timedelta
import time

def st_advanced_ma240_df_up(df_single):
    """
    實戰強化版：年線扣抵預判 + 趨勢斜率 + 帶量轉強
    適用於：台灣 50、中型 100 等權值股
    """
    # 基礎檢查：計算 MA240 需要 240 筆，判斷斜率與扣抵需要更多資料
    # 建議傳入至少 260 筆資料
    if df_single.empty or len(df_single) < 241:
        return False, {}

    # 1. 計算技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 240 天前的價格 (即將被踢除的舊資料)
    price_240_ago = df_single['close'].iloc[-240]

    # --- 核心邏輯：扣抵與斜率判斷 ---
    
    # 條件 A: 扣抵翻揚 (今日收盤 > 240 天前收盤)
    # 這是確保「年線不下墜」的數學保證
    is_tipping_up = today['close'] > price_240_ago
    
    # 條件 B: 年線斜率不為負 (今日 MA240 >= 昨日 MA240)
    is_ma240_not_falling = today['MA240'] >= yesterday['MA240']

    # --- 輔助篩選條件 ---
    
    # 條件 C: 距離年線 3% 以內 (位階不可過高)
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    is_near_ma240 = abs(dist_ratio) <= 0.03
    
    # 條件 D: 帶量轉強 (今日量 > 5日均量 1.5 倍)
    # 對於大型股，1.5 倍以上的量更有代表性
    vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
    is_volume_up = today['Trading_Volume'] > vol_ma5 * 1.5 if vol_ma5 > 0 else False

    # --- 綜合判斷 (Hit Logic) ---
    # 核心：必須符合「扣抵翻揚」且「年線不下彎」，且在「年線附近」有「攻擊量」
    is_hit = is_tipping_up and is_ma240_not_falling and is_near_ma240 and is_volume_up
    
    # --- 輸出資訊整理 ---
    # 計算扣抵差幅 (越高代表年線往上拉的力道越猛)
    diff_240_ratio = (today['close'] - price_240_ago) / price_240_ago
    
    status = "真突破/回測" if is_tipping_up else "假突破(扣抵壓力大)"
    
    info = {
        "收盤": today['close'],
        "扣抵差幅": f"{round(diff_240_ratio*100, 2)}%",
        "年線斜率": "上揚/平穩" if is_ma240_not_falling else "下彎",
        "量比": f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x",
        "策略狀態": status
    }

    print(f"is_hit:{is_hit}, info:{info}\n")
    return is_hit, info


# --- 1. 策略邏輯函數 (具備自主抓資料權力) ---
def st_advanced_ma240_df(df_single):
    """
    年線上下3% + 均線糾結 + 帶量轉強
    """
      
    # 基礎檢查：資料量需足夠計算年線
    if df_single.empty or len(df_single) < 240:
        return False, {}

    # 計算技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    
    today = df_single.iloc[-1]

    # --- 篩選條件 ---
    # 條件 1: 距離年線 3% 以內
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    is_near_ma240 = abs(dist_ratio) <= 0.03
    
    # 條件 2: 均線糾結 (5, 20, 60MA 差距在 5% 內，代表中短期成本一致)
    ma_list = [today['MA5'], today['MA20'], today['MA60']]
    dispersion = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_converged = dispersion < 0.05
    
    # 條件 3: 帶量 (今日量 > 5日均量 1.2倍)
    vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
    is_volume_up = today['Trading_Volume'] > vol_ma5 * 1.2 if vol_ma5 > 0 else False

    # 綜合判斷：只要靠近年線且「糾結」或「帶量」其中之一符合即可視為預備股
    is_hit = is_near_ma240 and (is_converged or is_volume_up)
    
    status = "年線上方整理" if dist_ratio > 0 else "年線下方待突破"
    
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio*100, 2)}%",
        "策略狀態": status,
        "糾結度": f"{round(dispersion*100, 2)}%",
        "量比": f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x"
    }

    #print(f"st_advanced_ma240(  df_single  ) is_hit:{is_hit}   info:{info}")
    
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
        "策略狀態": status
    }

    print(f"st_advanced_ma240 is_hit:{is_hit}   info:{info}")
    
    return is_hit, info
