import pandas as pd


def mon_ma5_break_advanced(df_single):
    #def strong_runup_high_volume_reversal(df_single):
    """
    進階策略：前段強拉創新高 + 爆量 + 殺長黑 + 高乖離（短線過熱見頂與出貨反轉警訊）
    """
    # 基礎檢查：需要至少 60 筆資料來確保均線與均量計算穩定
    if df_single.empty or len(df_single) < 60:
        return False, {}
        
    # 1. 計算技術指標與量能均線
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['Vol_MA20'] = df_single['volume'].rolling(20).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 前置強拉條件：過去 5 個交易日累積漲幅顯著（例如超過 15%）
    prev_5d_close = (
        df_single.iloc[-6]['close'] if len(df_single) >= 6 else df_single.iloc[0]['close']
    )
    
    runup_pct = (today['close'] - prev_5d_close) / prev_5d_close
    is_strong_runup = runup_pct > 0.15
    
    # 3. 創高條件：今日的 max 欄位達到過去 20 日內的最高點
    max_20 = df_single['max'].rolling(20).max().iloc[-1]
    is_new_high = today['max'] >= max_20
    
    # 4. 爆量條件：今日成交量大於 20 日均量的 2 倍以上
    is_volume_surge = today['volume'] > (today['Vol_MA20'] * 2.0)
    
    # 5. 殺長黑條件：收盤價低於開盤價（黑K），且當日跌幅超過 3%
    daily_return = (today['close'] - yesterday['close']) / yesterday['close']
    is_long_black = (today['close'] < today['open']) and (daily_return < -0.03)
    
    # 6. 高乖離條件：收盤價與 20 日均線的正乖離率超過 10%
    disparity = (today['close'] - today['MA20']) / today['MA20']
    is_high_disparity = disparity > 0.10
    
    # 綜合判斷：同時滿足強拉、創高、爆量、殺長黑與高乖離
    is_hit = (
        is_strong_runup
        and is_new_high
        and is_volume_surge
        and is_long_black
        and is_high_disparity
    )

    # 輸出資訊整理
    status = "🚨 強拉創高後爆量殺長黑(高檔過熱反轉警訊)" if is_hit else "安全/續抱"
    
    info = {
        "收盤": today['close'],
        "20日均線": round(today['MA20'], 2),
        "當日漲跌幅": f"{round(daily_return * 100, 2)}%",
        "近5日累積漲幅": f"{round(runup_pct * 100, 2)}%",
        "正乖離率": f"{round(disparity * 100, 2)}%",
        "監控狀態": status,
    }

    return is_hit, info

def mon_ma5_break_advanced(df_single):
    #def mon_ma5_break_with_recent_volume(df_single):
    """
    進階策略：5日線失守 + 最近 3 日內曾出現極端爆量（高檔密集換手與套牢警訊）
    """
    # 基礎檢查：需要至少 60 筆資料來確保均線與均量計算穩定
    if df_single.empty or len(df_single) < 60:
        return False, {}

    # 1. 計算技術指標與量能均線
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()

    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]

    # 2. 基礎破線條件：今日跌破 5 日線
    was_above_ma5 = yesterday['close'] >= yesterday['MA5']
    is_below_ma5 = today['close'] < today['MA5']
    is_ma5_break = was_above_ma5 and is_below_ma5

    # 3. 🌟 範圍爆量條件：檢查最近 3 個交易日（含今日）內，是否有任何一日出現極端爆量（> 2倍 20日均量）
    recent_3d = df_single.iloc[-3:]
    has_recent_high_volume = any(
        row['Trading_Volume'] > (row['Vol_MA20'] * 2.0) 
        for _, row in recent_3d.iterrows() if row['Vol_MA20'] > 0
    )

    # 4. 位階過濾：確保原本處於多頭架構中（收盤價高於 MA20）
    is_uptrend = today['close'] > today['MA20']

    # 綜合判斷
    is_hit = is_uptrend and is_ma5_break and has_recent_high_volume

    # 輸出資訊整理
    price_change_pct = (today['close'] - yesterday['close']) / yesterday['close']
    status = "🚨 5日線破線且3日內伴隨爆量(重度套牢/出貨警訊)" if is_hit else "安全/續抱"

    info = {
        "收盤": today['close'],
        "5日線": round(today['MA5'], 2),
        "當日漲跌幅": f"{round(price_change_pct * 100, 2)}%",
        "近3日是否有極端爆量": "是" if has_recent_high_volume else "否",
        "監控狀態": status
    }

    return is_hit, info

def mon_ma5_break_advanced_old(df_single):
    """
    進階 5 日線失守監控：5日線破線 + 扣抵向下 + 帶量下殺 + 黑K或長上影線反轉
    """
    # 基礎檢查：需要至少 65 筆資料來確保均線與扣抵值計算穩定
    if df_single.empty or len(df_single) < 65:
        return False, {}

    df_single = df_single.copy() # 建立複本確保安全

    # 1. 計算技術指標、量能均線與 5日線扣抵值
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    df_single['MA5_Deduction'] = df_single['close'].shift(5)

    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]

    # 2. 基礎破線條件：今日跌破 5 日線
    was_above_ma5 = yesterday['close'] >= yesterday['MA5']
    is_below_ma5 = today['close'] < today['MA5']
    is_ma5_break = was_above_ma5 and is_below_ma5

    # 3. 扣抵向下條件：今日收盤價低於 5 天前的扣抵值
    is_deduction_down = today['close'] < today['MA5_Deduction']

    # 4. 帶量條件：成交量大於 20 日均量 1.2 倍以上
    vol_ma20 = today['Vol_MA20']
    is_heavy_volume = today['Trading_Volume'] > (vol_ma20 * 1.2) if vol_ma20 > 0 else False

    # 5. 跌幅擴大條件：當日實際跌幅超過 1.5%
    price_change_pct = (today['close'] - yesterday['close']) / yesterday['close']
    is_significant_drop = price_change_pct < -0.015  

    # 6. 🌟 K 棒形態防呆與過濾 (對應欄位名稱若為 high/low 請自行替換)
    high_col = 'high' if 'high' in df_single.columns else ('max' if 'max' in df_single.columns else 'close')
    low_col = 'low' if 'low' in df_single.columns else ('min' if 'min' in df_single.columns else 'close')

    is_black_candle = today['close'] < today['open']
    
    total_range = today[high_col] - today[low_col]
    upper_shadow = today[high_col] - max(today['open'], today['close'])
    
    # 振幅大於 3% 且上影線佔總振幅 35% 以上，定義為有效長上影線
    range_pct = total_range / yesterday['close'] if yesterday['close'] > 0 else 0
    is_long_upper_shadow = (range_pct > 0.03) and ((upper_shadow / total_range) > 0.35) if total_range > 0 else False

    # 形態確認：必須是實體黑K，或者具備長上影線且伴隨回檔
    is_valid_k_pattern = is_black_candle or is_long_upper_shadow

    # 7. 位階過濾：確保大方向處於多頭架構中（收盤價高於 MA20）
    is_uptrend = today['close'] > today['MA20']

    # 綜合判斷
    is_hit = (
        is_uptrend 
        and is_ma5_break 
        and is_deduction_down 
        and is_heavy_volume 
        and is_significant_drop 
        and is_valid_k_pattern
    )

    # 輸出資訊整理
    vol_ratio = round(today['Trading_Volume'] / vol_ma20, 2) if vol_ma20 > 0 else 0
    status = "🚨 5日線帶量下殺與反轉形態(短線轉弱)" if is_hit else "安全/續抱"

    info = {
        "收盤": today['close'],
        "5日線": round(today['MA5'], 2),
        "當日漲跌幅": f"{round(price_change_pct * 100, 2)}%",
        "量比(vs MA20)": f"{vol_ratio}x",
        "是否為黑K": "是" if is_black_candle else "否",
        "是否具長上影線": "是" if is_long_upper_shadow else "否",
        "監控狀態": status
    }

    return is_hit, info

def mon_high_vol_exit(df_single):
    """
    出場/風險監控：高檔極端爆量與出貨形態綜合判斷（含黑K長度與振幅過濾防呆）
    """
    # 基礎檢查：需要至少 120 筆以上資料來確保均線與滾動視窗計算穩定
    if df_single.empty or len(df_single) < 120:
        return False, {}

    # 1. 計算技術指標與位階
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['Close_Max60'] = df_single['close'].rolling(60).max() # 過去 60 個交易日最高價 (約一季高檔)
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    df_single['Vol_Max60'] = df_single['Trading_Volume'].rolling(60).max()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # --- 核心判斷 1: 高檔位階過濾 ---
    is_above_ma = (today['close'] > today['MA20']) and (today['close'] > today['MA60'])
    is_near_high = today['close'] >= (today['Close_Max60'] * 0.95)
    is_at_high_level = is_above_ma and is_near_high
    
    # --- 核心判斷 2: 極端量能條件 (2.5倍均量且創60日天量) ---
    vol_ma20 = today['Vol_MA20']
    is_volume_multiple = today['Trading_Volume'] > (vol_ma20 * 2.5) if vol_ma20 > 0 else False
    is_rolling_max_vol = today['Trading_Volume'] >= today['Vol_Max60']
    is_extreme_volume = is_volume_multiple and is_rolling_max_vol
    
    # --- 核心判斷 3: 殺傷力 K 棒形態 (黑K與長上影線過濾) ---
    is_black_candle = today['close'] < today['open']
    
    # 計算實體黑K跌幅比例（開盤價減去收盤價佔開盤價的比例）
    body_drop_pct = (today['open'] - today['close']) / today['open']
    
    # 計算相較於昨日收盤的實際跌幅比例
    price_change_pct = (today['close'] - yesterday['close']) / yesterday['close']
    
    # 計算當日總振幅與上影線（欄位名稱改用 max 與 min）
    total_range = today['max'] - today['min']
    upper_shadow = today['max'] - max(today['open'], today['close'])
    
    # 🌟 【上影線防呆過濾】總振幅必須大於昨日收盤的 3%，且上影線佔總振幅 40% 以上才算有效長上影線
    range_pct = total_range / yesterday['close'] if yesterday['close'] > 0 else 0
    is_significant_range = range_pct > 0.03  # 總振幅大於 3%
    is_long_upper_shadow = is_significant_range and ((upper_shadow / total_range) > 0.4) if total_range > 0 else False
    
    # 🌟 【黑K殺傷力過濾】
    # 必須同時滿足：
    # 1. 確實收黑K (is_black_candle)
    # 2. 具備實質跌幅：實體黑K跌幅超過 1.5% (body_drop_pct > 0.015) 
    #    或者與昨日收盤相比實際跌幅超過 2.0% (price_change_pct < -0.02)
    # 藉此過濾掉微幅收黑的雜訊，確保具備足夠的下殺破壞力
    is_black_distribution = is_black_candle and (body_drop_pct > 0.015 or price_change_pct < -0.02)
    
    # 有效出貨形態：符合殺傷力的黑K出貨 或 具備足夠振幅的長上影線且伴隨回檔
    is_shadow_distribution = is_long_upper_shadow and price_change_pct < 0
    is_valid_distribution = is_black_distribution or is_shadow_distribution
    
    # --- 綜合判斷 (Hit Logic) ---
    is_hit = is_at_high_level and is_extreme_volume and is_valid_distribution
    
    # --- 輸出資訊整理 ---
    vol_ratio = round(today['Trading_Volume'] / vol_ma20, 2) if vol_ma20 > 0 else 0
    status = "🚨 高檔爆量見頂訊號(觸發出場)" if is_hit else "安全/續抱"
    
    info = {
        "收盤": today['close'],
        "開盤": today['open'],
        "最高": today['max'],
        "最低": today['min'],
        "是否符合高檔位階": "是(接近60日高點且在均線之上)" if is_at_high_level else "否",
        "當日漲跌幅": f"{round(price_change_pct * 100, 2)}%",
        "當日總振幅": f"{round(range_pct * 100, 2)}%",
        "實體黑K幅": f"{round(body_drop_pct * 100, 2)}%",
        "量比(vs MA20)": f"{vol_ratio}x",
        "是否創60日天量": "是" if is_rolling_max_vol else "否",
        "監控狀態": status
    }

    return is_hit, info
