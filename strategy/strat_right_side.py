import pandas as pd

def st_bottom_u_turn_mid100_rebirth(df_single):
    """
    ***st_bottom_u_turn 策略 A-3：中型 100 題材破滅 U 型底重生系統 (主力動能版)***
    
    【中型 100 核心篩選參數說明】
    1. 流動性防線：過去 20 日平均成交量需 >= 300 張，防止買進流動性窒息的殭屍股。
    2. 空間腰斬過濾：當前股價距離過去 240 日最高價至少跌了 50% (中型股吹泡沫破滅後的安全位階)。
    3. 時間沉澱：季線在年線下方連續沉澱至少 120 個交易日 (約半年，洗淨沒耐心的融資浮額)。
    4. 均線發散度放寬：短中期均線發散度限制放寬至 <= 8% (適應中型股第一根發動時常有的劇烈大紅K)。
    5. 動能甦醒加強：今日必收紅K，且成交量必須大於 20 日均量的 2.0 倍 (確認真主力資金進場換手)。
    
    【其餘基底架構承襲嚴選版】
    - 季線在年線下方 (60MA < 240MA)
    - 年線 5 日變動率 >= -1.0% (長線引力減速)
    - 季線扭轉向上 (今日 60MA > 昨日 60MA)
    - 短中期多頭排列 (5MA > 10MA > 20MA > 60MA)
    - 雙扣抵智能容許 (季線 5 日扣抵變動 <= 1.5%、年線 20 日扣抵變動 <= 2.0%)
    """
    # 確保資料量足夠計算時空濾網，包含年線與長線沉澱，基本需 300 筆以上
    if df_single.empty or len(df_single) < 300:
        return False, {}

    # --- 1. 計算基本技術指標 ---
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # --- 2. 流動性核心防線 (新增) ---
    # 中型股最怕型態漂亮但平時沒量，進得去出不來。日均量未達 300 張直接淘汰
    is_liquid = today['Vol_MA20'] >= 300
    if not is_liquid:
        return False, {}
    
    # --- 3. 時空前置過濾網 (配合中型股優化調整) ---
    # (A) 空間跌幅：中型股修正更深，卡死必須從一年(240日)最高點「腰斬」 50% 以上
    max_price_240d = df_single['max'].rolling(240).max().iloc[-1]
    is_dropped_enough = today['close'] <= (max_price_240d * 0.50)
    
    # (B) 時間沉澱：計算季線在年線下方的連續天數，過去 120 天必須天天都在年線下
    df_single['below_count'] = (df_single['MA60'] < df_single['MA240']).astype(int)
    consecutive_below_days = df_single['below_count'].rolling(120).sum().iloc[-1]
    is_sedimented_enough = consecutive_below_days >= 120
    
    # --- 4. 基本位階與趨勢檢查 ---
    is_below_ma240 = today['MA60'] < today['MA240']
    
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago != 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.01 
    
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    
    # --- 5. 扣抵值智能容許過濾 ---
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    ma60_deduct_change = (ma60_deduct_5d_later - ma60_deduct_today) / ma60_deduct_today if ma60_deduct_today > 0 else 0
    is_ma60_deduct_ok = ma60_deduct_change <= 0.015

    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220]
    ma240_deduct_change = (ma240_deduct_20d_later - ma240_deduct_today) / ma240_deduct_today if ma240_deduct_today > 0 else 0
    is_ma240_deduct_ok = ma240_deduct_change <= 0.02
    
    # --- 6. 均線發散度過濾 (配合中型股優化調整) ---
    # 中型股第一根突圍紅K往往拉得又急又快，發散度限制適度放寬至 8%，避免誤殺起漲飆股
    ma_list = [today['MA5'], today['MA10'], today['MA20']]
    ma_dispersion = (max(ma_list) - min(ma_list)) / today['MA20'] if today['MA20'] > 0 else 0
    is_ma_not_overheated = ma_dispersion <= 0.08

    # --- 7. 量能與動能甦醒判定 (配合中型股優化調整) ---
    is_triggered = today['close'] > today['open'] # 當日必收紅K
    # 甦醒量：中型股底部基期量極低，主力點火引導右側攻擊，成交量必須大於 20 日均量的 2.0 倍
    is_volume_revived = today['Trading_Volume'] >= (today['Vol_MA20'] * 2.0)
    
    # --- 8. 綜合判定 (10 大條件完全交集) ---
    is_hit = (is_liquid and is_dropped_enough and is_sedimented_enough and is_below_ma240 and 
              is_ma240_stable and is_ma60_turning_up and is_short_trend_bullish and 
              is_ma60_deduct_ok and is_ma240_deduct_ok and is_ma_not_overheated and 
              is_triggered and is_volume_revived)

    # 描述量能型態供日誌分析
    vol_ratio = today['Trading_Volume'] / today['Vol_MA5'] if today['Vol_MA5'] > 0 else 0
    is_vol_type_A = vol_ratio >= 1.5
    is_vol_type_B = (today['Trading_Volume'] > yesterday['Trading_Volume']) and (today['Trading_Volume'] > today['Vol_MA5'])
    vol_style = "無量空漲"
    if is_vol_type_A and is_vol_type_B:
        vol_style = "雙重觸發【主力暴發攻擊量】與【溫和遞增量】"
    elif is_vol_type_A:
        vol_style = "型態 A：底部主力強勢攻擊量(>=1.5x 5MA)"
    elif is_vol_type_B:
        vol_style = "型態 B：溫和放量遞增"
    
    status = "[A-3 中型100重生底] 腰斬股低檔橫盤半年，主力帶 2 倍大補量點火！" if is_hit else "未觸發訊號"
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    info = {
        "收盤": today['close'],
        "均線發散度": f"{round(ma_dispersion * 100, 2)}%",
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "240日高點跌幅": f"{round((1 - today['close']/max_price_240d)*100, 2)}%",
        "季線年線下沉天數": int(consecutive_below_days),
        "20日均量(張)": int(today['Vol_MA20']),
        "今日量比20MA": f"{round(today['Trading_Volume'] / today['Vol_MA20'], 2)}x",
        "量能風格": vol_style,
        "策略狀態": status
    }
    
    if is_hit:
        print(f"【觸發訊號】st_bottom_u_turn_mid100_rebirth is_hit:{is_hit}")
        print(f"-> 流動性安全: {is_liquid} (20MA日均量: {int(today['Vol_MA20'])}張)")
        print(f"-> 空間檢查(腰斬): {is_dropped_enough} (跌幅: {info['240日高點跌幅']})")
        print(f"-> 時間沉澱: {consecutive_below_days}天 | 主力甦醒量: {info['今日量比20MA']}")
        
    return is_hit, info


def st_bottom_u_turn(df_single):
    """
    ***st_bottom_u_turn 策略 A-2：題材破滅 U 型碗底翻揚系統 (20260703 究極嚴選版)***
    優化重點：
    1. 雙扣抵容許區間 ➡️ 留下華碩，洗掉結構不穩股。
    2. 均線發散度限制 ➡️ 洗掉短線暴衝、均線拉太開的精銳與祥碩。
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 1. 技術指標計算
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 基本位階與趨勢檢查
    is_below_ma240 = today['MA60'] < today['MA240']
    
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.01 
    
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    
    # 🌟 優化一：扣抵值智能容許過濾 (避免誤殺華碩)
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    ma60_deduct_change = (ma60_deduct_5d_later - ma60_deduct_today) / ma60_deduct_today if ma60_deduct_today > 0 else 0
    is_ma60_deduct_ok = ma60_deduct_change <= 0.015

    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220]
    ma240_deduct_change = (ma240_deduct_20d_later - ma240_deduct_today) / ma240_deduct_today if ma240_deduct_today > 0 else 0
    is_ma240_deduct_ok = ma240_deduct_change <= 0.02

    print(f"ma240_deduct_today: {ma240_deduct_today} | ma240_deduct_20d_later: {ma240_deduct_20d_later} | ma240_deduct_change: {ma240_deduct_change}")
    
    # 🌟 優化二：均線發散度過濾 (精銳、祥碩殺手)
    ma_list = [today['MA5'], today['MA10'], today['MA20']]
    ma_dispersion = (max(ma_list) - min(ma_list)) / today['MA20'] if today['MA20'] > 0 else 0
    is_ma_not_overheated = ma_dispersion <= 0.06  # 限制短中期均線乖離在 6% 以內

    # 3. 量能與觸發判定
    is_triggered = today['close'] > today['open']
    
    # 4. 綜合判定
    is_hit = (is_below_ma240 and is_ma240_stable and is_ma60_turning_up and 
              is_short_trend_bullish and is_triggered and 
              is_ma60_deduct_ok and is_ma240_deduct_ok and is_ma_not_overheated)

    print(f"Below240: {is_below_ma240} | Stable240: {is_ma240_stable} | MA60Up: {is_ma60_turning_up} | ShortBull: {is_short_trend_bullish} | Triggered: {is_triggered}")
    print(f"ma60_deduct: {is_ma60_deduct_ok} | ma240_deduct: {is_ma240_deduct_ok} | not_overheated: {is_ma_not_overheated}")
    
    status = "[A-2 鑽石碗底] 均線溫和凝聚＋雙扣抵大吉！" if is_hit else "未觸發訊號"
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    info = {
        "收盤": today['close'],
        "均線發散度": f"{round(ma_dispersion * 100, 2)}%",
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "策略狀態": status
    }
        
    return is_hit, info

def st_bottom_u_turn_2026070302(df_single):
    """
    ***st_bottom_u_turn_2026070302 策略 A-2：題材破滅 U 型碗底翻揚系統 (純結構動能＋中長線雙扣抵預報版)***

    【核心篩選條件 (同時滿足才觸發 is_hit)】
    1. 基底檢查：季線仍在年線下方 (60MA < 240MA)，定位長期底部。
    2. 年線減速：年線 5 日變動率 >= -1.0%，確認長線跌勢已開始減速走平。
    3. 中線轉折：季線扭轉向上 (今日 60MA > 昨日 60MA)。
    4. 趨勢成形：短中期均線展現標準多頭排列 (5MA > 10MA > 20MA > 60MA)。
    5. 安全點火：當日必須收紅K (收盤價 > 開盤價)。
    
    ※ 註：季線與年線的扣抵走勢預報僅作為操作輔助與狀態描述，不計入 is_hit 的硬性門檻。
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
    
    # 🌟 5-A. 季線未來 5 日扣抵值走勢預報 (看短期發動續航力)
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    if ma60_deduct_5d_later < ma60_deduct_today:
        ma60_forecast = "輕鬆助漲 (扣抵走低)"
    else:
        ma60_forecast = "壓力引力 (扣抵走高)"

    # 🌟 5-B. 新增：年線未來 20 日 (一個月) 扣抵值走勢預報 (看大結構轉骨潛力)
    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220] # 20天後扣抵的位置
    if ma240_deduct_20d_later < ma240_deduct_today:
        ma240_forecast = "🔥 大吉！一年前股價正崩盤溜滑梯，有利突破年線後「長線轉骨」成主升段"
    else:
        ma240_forecast = "⏳ 橫盤！一年前股價在高檔死盤，年線下彎引力仍重，過年線後震盪難免"

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
    
    # 8. 綜合獨立判定
    is_hit = is_below_ma240 and is_ma240_stable and is_ma60_turning_up and is_short_trend_bullish and is_triggered
    status = f"[A-2 碗底翻揚] 季線轉正＋均線小多頭！紅K點火確認 ({vol_style})" if is_hit else "未觸發訊號"
    
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
        "季線趨勢": f"翻揚向上 ({ma60_forecast})",
        "長線年線扣抵預報": ma240_forecast,  # 新增年線大預報
        "今日量比": f"{round(vol_ratio, 2)}x",
        "策略操作": action_strategy,
        "策略狀態": status
    }
    
    if is_hit:
        print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
        
    return is_hit, info

def st_bottom_u_turn_v2026070301(df_single):
    """
    ***st_bottom_u_turn_v2026070301 策略 A-2：題材破滅 U 型碗底翻揚系統 (雙扣抵結構硬過濾版)***
    
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
    ***st_bottom_u_turn_v20260703 策略 A-2：題材破滅 U 型碗底翻揚系統 ***
    
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
