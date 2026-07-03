import pandas as pd

def st_bottom_u_turn_v2026070301(df_single):
    """
    ***策略 A-2：題材破滅 U 型碗底翻揚系統 (雙扣抵結構硬過濾版)***
    
    核心邏輯：
    1. 位階限制：季線（60MA）在年線（240MA）下方，確保整體大結構處於低檔沉澱。
    2. 長線賣壓鈍化：年線下彎力道減速（5日內變動率 > -1.0%）。
    3. 靈魂解套訊號：季線（60MA）扭轉向上。
    4. 季線扣抵過濾：未來 5 日扣抵值必須走低，確保季線翻揚具備強力「結構性助漲」續航力。
    5. 年線扣抵過濾：未來 20 日扣抵值必須走低，確保上方年線魔王賣壓已實質減輕，利於長線轉骨。
    6. 小多頭排列：短期與中期均線整齊發散（5MA > 10MA > 20MA > 60MA）。
    7. 紅K保險絲：當日必須收紅K（Close > Open）。
    """
    # 確保資料量足夠計算 240MA (加上緩衝至少需 260 筆)
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 1. 計算核心技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 基底檢查：季線仍在年線下方
    is_below_ma240 = today['MA60'] < today['MA240']
    
    # 3. 年線減速檢查：限制 5 日變動率放寬至 1.0%
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.01 
    
    # 4. 中線定海神針：季線（60MA）扭轉向上
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    # 🌟 5-A. 【硬過濾一】季線未來 5 日扣抵值必須走低 (拒絕硬拔的虛胖轉正)
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    is_ma60_deduct_ok = ma60_deduct_5d_later < ma60_deduct_today

    # 🌟 5-B. 【硬過濾二】年線未來 20 日扣抵值必須走低 (確保年線引力減輕，有利大波段)
    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220]
    is_ma240_deduct_ok = ma240_deduct_20d_later < ma240_deduct_today

    # 6. 趨勢成形：短中期均線在年線下方展現標準多頭排列
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    
    # 7. 【安全保險絲】當日必須收紅K
    is_triggered = today['close'] > today['open']
    
    # 計算量能比例（純資訊描述）
    vol_ratio = today['Trading_Volume'] / today['Vol_MA5'] if today['Vol_MA5'] > 0 else 0
    is_vol_type_A = vol_ratio >= 1.5
    is_vol_type_B = (today['Trading_Volume'] > yesterday['Trading_Volume']) and (today['Trading_Volume'] > today['Vol_MA5'])
    
    vol_style = "無量空漲 / 籌碼真空"
    if is_vol_type_A and is_vol_type_B:
        vol_style = "雙重觸發【暴發攻擊量】與【溫和遞增量】"
    elif is_vol_type_A:
        vol_style = "型態 A：底部暴發攻擊量(>=1.5x)"
    elif is_vol_type_B:
        vol_style = "型態 B：溫和放量遞增"
    
    # 🌟 8. 綜合獨立判定 (正式加入雙扣抵值過濾條件)
    is_hit = (is_below_ma240 and is_ma240_stable and is_ma60_turning_up and 
              is_short_trend_bullish and is_triggered and 
              is_ma60_deduct_ok and is_ma240_deduct_ok)
              
    status = f"[A-2 嚴選碗底] 雙扣抵大吉＋季線轉正！最強轉骨起漲點 ({vol_style})" if is_hit else "未觸發訊號"
    
    # 9. 計算與年線的距離並產生操作策略建議
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    if dist_ratio < -0.05:
        action_strategy = "地下室反彈，年線附近停利"
    elif dist_ratio <= 0:
        action_strategy = "決戰天花板，注意年線反壓"
    else:
        action_strategy = "破繭而出，站穩年線看長線"
        
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線5日變動": f"{round(ma240_slope_5d * 100, 2)}%",
        "季線趨勢": "翻揚向上 (結構助漲)" if is_ma60_turning_up else "依舊下彎",
        "今日量比": f"{round(vol_ratio, 2)}x",
        "策略操作": action_strategy,
        "策略狀態": status
    }
    
    if is_hit:
        print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
        
    return is_hit, info

def st_bottom_u_turn_v20260703(df_single):
    """
    ***策略 A-2：題材破滅 U 型碗底翻揚系統***
    
    核心邏輯：
    1. 位階限制：季線（60MA）在年線（240MA）下方，確保整體大結構處於低檔沉澱，並允許當日股價強勢穿透年線。
    2. 長線賣壓鈍化：年線下彎力道大幅減速（5日內變動率 > -0.5%），排除剛崩盤下墜的股票。
    3. 靈魂解套訊號：季線（60MA）扭轉向上，代表過去一整個季度的低檔換手盤正式轉為多頭贏家。
    4. 小多頭排列：短期與中期均線整齊發散（5MA > 10MA > 20MA > 60MA），右側攻擊動能成形。
    """
    # 確保資料量足夠計算 240MA (加上緩衝至少需 260 筆)
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 1. 計算核心技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 基底檢查：季線仍在年線下方，確保人在地下室，允許今日收盤衝過年線
    is_below_ma240 = today['MA60'] < today['MA240']
    
    # 3. 年線減速檢查：限制 5 日變動率，確保年線已高度走緩，拒絕急墜股
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    #is_ma240_stable = ma240_slope_5d >= -0.005  # 5天內下彎不超過 0.5%

    is_ma240_stable = ma240_slope_5d >= -0.01  # 5天內下彎不超過 0.5%
    
    # 4. 【核心靈魂】中線定海神針：季線（60MA）必須止跌翻揚轉向向上
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    # 5. 趨勢成形：短中期均線在年線下方展現標準多頭排列
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    print(f"today['MA5']: {today['MA5']} | today['MA10']: {today['MA10']} | today['MA20']: {today['MA20']} | today['MA60']: {today['MA60']} ")

    
    # 6. 右側發動表態：量能雙軌判定
    vol_ratio = today['Trading_Volume'] / today['Vol_MA5'] if today['Vol_MA5'] > 0 else 0
    
    is_vol_type_A = vol_ratio >= 1.5
    is_vol_type_B = (today['Trading_Volume'] > yesterday['Trading_Volume']) and (today['Trading_Volume'] > today['Vol_MA5'])
    
    is_volume_ok = is_vol_type_A or is_vol_type_B
    #is_triggered = today['close'] > today['open'] and is_volume_ok
    is_triggered = today['close'] > today['open']
    
    # 詳細型態文字描述
    vol_style = "未放量"
    if is_vol_type_A and is_vol_type_B:
        vol_style = "雙重觸發【暴發攻擊量】與【溫和遞增量】"
    elif is_vol_type_A:
        vol_style = "型態 A：底部暴發攻擊量(>=1.5x)"
    elif is_vol_type_B:
        vol_style = "型態 B：溫和放量遞增"

    print(f"Below240: {is_below_ma240} | Stable240: {is_ma240_stable} | MA60Up: {is_ma60_turning_up} | ShortBull: {is_short_trend_bullish} | Triggered: {is_triggered}")
    
    # 7. 綜合獨立判定
    is_hit = is_below_ma240 and is_ma240_stable and is_ma60_turning_up and is_short_trend_bullish and is_triggered
    status = f"[A-2 碗底翻揚] 季線轉正＋均線小多頭！人在年線下安全伏擊點火 ({vol_style})" if is_hit else "未觸發訊號"
    
    # 8. 計算與年線的距離並動態產生簡單的操作策略建議
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    if dist_ratio < -0.05:
        action_strategy = "地下室反彈，年線附近停利"
    elif dist_ratio <= 0:
        action_strategy = "決戰天花板，注意年線反壓"
    else:
        action_strategy = "破繭而出，站穩年線看長線"
        
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線5日變動": f"{round(ma240_slope_5d * 100, 2)}%",
        "季線趨勢": "翻揚向上" if is_ma60_turning_up else "依舊下彎",
        "今日量比": f"{round(vol_ratio, 2)}x",
        "策略操作": action_strategy,  # 新增此欄位
        "策略狀態": status
    }
    
    #if is_hit:
    #   print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
    print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
        
    return is_hit, info
