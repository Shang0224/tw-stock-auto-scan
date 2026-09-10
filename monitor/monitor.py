import pandas as pd

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


def mon_high_vol_exit_old(df_single):
    """
    出場/風險監控：高檔爆量長黑警示（一個月高點位階過濾）
    核心邏輯：一個月高檔確認(非底部反彈) + 極端量能 + 有殺傷力的黑K與跌幅
    """
    # 基礎檢查：需要至少 120 筆以上資料來計算 120 天天量
    if df_single.empty or len(df_single) < 120:
        return False, {}

    # 1. 計算技術指標
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['Close_Max20'] = df_single['close'].rolling(20).max() # 過去 20 個交易日最高價 (約一個月)
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    df_single['Vol_Max120'] = df_single['Trading_Volume'].rolling(120).max()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # --- 核心關鍵：一個月高檔位階過濾 ---
    # 條件 1: 價格必須在 MA20 之上 (短線多頭結構未破)
    is_above_ma20 = today['close'] > today['MA20']
    
    # 條件 2: 價格必須位在一個月內的高檔區 (收盤價大於等於過去 20 天最高價的 90%)
    is_near_monthly_high = today['close'] >= (today['Close_Max20'] * 0.90)
    
    is_at_high_level = is_above_ma20 and is_near_monthly_high
    
    # --- 核心量能條件 ---
    vol_ma20 = today['Vol_MA20']
    is_volume_multiple = today['Trading_Volume'] > (vol_ma20 * 2.0) if vol_ma20 > 0 else False
    is_rolling_high = today['Trading_Volume'] >= today['Vol_Max120']
    is_extreme_volume = is_volume_multiple or is_rolling_high
    
    # --- 價位與幅度條件 ---
    is_black_candle = today['close'] < today['open']
    
    # 計算實體黑K跌幅比例 (例如跌超過 1.2%)
    body_drop_pct = (today['open'] - today['close']) / today['open']
    is_body_large = body_drop_pct > 0.012 
    
    # 計算相較於昨日收盤的實際跌幅 (例如跌超過 2.0%)
    price_change_pct = (today['close'] - yesterday['close']) / yesterday['close']
    is_price_down_heavy = price_change_pct < -0.02
    
    # 綜合價位判定：必須是收黑K，且「實體夠大」或「當日跌幅夠深」
    is_valid_distribution = is_black_candle and (is_body_large or is_price_down_heavy)
    
    # --- 綜合判斷 (Hit Logic) ---
    is_hit = is_at_high_level and is_extreme_volume and is_valid_distribution
    
    # --- 輸出資訊整理 ---
    vol_ratio = round(today['Trading_Volume'] / vol_ma20, 2) if vol_ma20 > 0 else 0
    status = "🚨 真實高檔有效爆量長黑(觸發出場)" if is_hit else "安全/續抱(非一個月高檔)"
    
    info = {
        "收盤": today['close'],
        "開盤": today['open'],
        "是否符合一月高檔": "是(接近20日高點且在MA20上)" if is_at_high_level else "否",
        "當日跌幅": f"{round(price_change_pct * 100, 2)}%",
        "實體黑K幅": f"{round(body_drop_pct * 100, 2)}%",
        "量比(vs MA20)": f"{vol_ratio}x",
        "是否創120日天量": "是" if is_rolling_high else "否",
        "監控狀態": status
    }

    #print(f"is_hit:{is_hit}, info:{info}\n")
    return is_hit, info
