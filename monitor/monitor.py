import pandas as pd

def mon_high_vol_exit(df_single):
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

    print(f"is_hit:{is_hit}, info:{info}\n")
    return is_hit, info
