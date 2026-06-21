from FinMind.data import DataLoader
import pandas as pd
from datetime import datetime, timedelta
import time

def st_bottom_rebound(df_single):
    """
    ***底部轉強*** 負乖離>20%, 年線下跌趨緩接近走平
    """
      
   # 基礎檢查：資料量需足夠計算年線 (240日) 與年線斜率 (需額外20日觀察期，共260日最安全)
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 計算技術指標
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    
    # 取出今日與歷史資料
    today = df_single.iloc[-1]
    
    # --- Bottom Breakout 核心篩選邏輯 ---
    
    # 1. 條件 1: 股價必須在年線下方
    is_below_ma240 = today['close'] < today['MA240']
    
    # 2. 條件 2: 負乖離率大於等於 20% (即 dist_ratio <= -20%)
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    is_oversold = dist_ratio <= -0.20
    
    # 3. 條件 3: 年線下跌趨緩 (計算過去 20 個交易日的年線變動百分比)
    # 若變動率大於 -0.5%，代表下墜慣性已踩煞車，開始接近水平橫盤
    ma240_20d_ago = df_single['MA240'].iloc[-21] # 20天前的年線位置
    ma_slope_20d = (today['MA240'] - ma240_20d_ago) / ma240_20d_ago if ma240_20d_ago > 0 else 0
    is_flattening = ma_slope_20d > -0.005  # -0.5% 以內視為趨緩或走平

    # 綜合判斷：三個條件必須同時成立 (左側超跌且築底跡象顯現)
    #is_hit = is_below_ma240 and is_oversold and is_flattening
    is_hit = is_below_ma240 and is_flattening
    
    # 動態判斷狀態描述
    if is_flattening:
        status = "年線走平築底中"
    else:
        status = "年線仍持續下跌"
    
    # 組裝回傳資訊
    info = {
        "收盤": today['close'],
        "年線位置": round(today['MA240'], 2),
        "負乖離率": f"{round(dist_ratio * 100, 2)}%",
        "年線20日斜率": f"{round(ma_slope_20d * 100, 2)}%",
        "狀態": status
    }

    print(f"st_bottom_breakout( df_single ) is_hit:{is_hit} info:{info}")
    
    return is_hit, info
