import pandas as pd

# ==============================================================================
# 💡 策略邏輯備忘註腳 (Strategy Footnotes & Design Philosophy)
# ==============================================================================
# 1. 核心哲學：本策略專門捕捉「破底翻」或「惡意洗盤後 V 型拔地而起」的暴利黑馬股。
# 2. 徹底揚棄「左側摸底」的左側猜測，改用今日「實體紅K 創 20 日新高」作為右側動能確認的進場依據。
# 3. 承認並解鎖「洗盤時差 (Washout Lag)」：
#    - 主力在拉抬前，往往會利用市場恐慌，刻意砸盤殺破「前 60 日歷史新低」(製造崩盤假象)。
#    - 關鍵在於：洗盤當天成交量必須呈現「窒息量縮」(代表籌碼已被主力鎖死，散戶絕望繳械)。
#    - 隨後主力迅速在 10 天之內發動總攻，拉出爆量長紅並一舉強勢站回季線（生命線）。
#    - 因此，本策略引進「時空記憶體」，只要過去 10 天(兩週)曾出現主力惡意挖坑洗盤的足跡，
#      搭配「今日」主力爆量點火、價格全面復活，即視為最完美的短線右側發動點。
# ==============================================================================

def st_washout_phoenix(df_single):
    """強力洗盤復活策略
    
    【策略靈魂】: 
    專抓大週期跌深、年線減速走平，且過去 10 天內出現「惡意創 60 日新低」的窒息量洗盤，
    今日突然拉出帶量紅K，一舉站回季線並創 20 日新高的「破底翻」暴利黑馬股。
    """
    # 1. 基礎長度防護門檻（ need 滿足 MA240 與 60 日滾動窗格需求 ）
    if len(df_single) < 310:
        return False, {"策略狀態": "資料天數不足(<310)"}
        
    # 定義時間指針：永遠鎖定你系統切出的 df_single 最後一列（即今日盤後最新數據）
    today = df_single.iloc[-1]
    
    # 2. 量能指標安全補算（若你的 all_df 外部沒算，內部自動補齊）
    if 'MA5_volume' not in df_single.columns:
        df_single['MA5_volume'] = df_single['volume'].rolling(5).mean()
    if 'MA20_volume' not in df_single.columns:
        df_single['MA20_volume'] = df_single['volume'].rolling(20).mean()
        
    today_ma5_vol = df_single['MA5_volume'].iloc[-1]
    today_ma20_vol = df_single['MA20_volume'].iloc[-1]

    # =========================================================================
    # 核心條件一：均線與趨勢濾網（鎖定長期大底部）
    # =========================================================================
    # 條件 A: 處於低檔空頭排列 (季線在年線下方，確保不是追在高檔)
    is_in_bottom_zone = today['MA60'] < today['MA240']
    
    # 條件 B: 年線下彎速度走平 (計算年線 5 日斜率，確保引力衰減中)
    ma240_5d_ago = df_single['MA240'].iloc[-5]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago
    is_ma240_flattening = ma240_slope_5d >= -0.015  # 下跌斜率收斂在 -1.5% 以內
    
    # 條件 C: 今日實體強勢站回生命線 (今日收盤價必須站上季線)
    is_above_lifeline = today['close'] >= today['MA60']
    
    if not (is_in_bottom_zone and is_ma240_flattening and is_above_lifeline):
        return False, {"策略狀態": "大週期均線型態不符（未過趨勢濾網）"}

    # =========================================================================
    # 核心條件二：過去 10 天惡意洗盤判定（破底翻骨架）
    # =========================================================================
    # 觀測窗格：切出過去 10 天 (不含今天) 的歷史 K 線
    past_10d_window = df_single.iloc[-11:-1]
    
    # 找出洗盤發生前、更早的 60 日最低價邊界
    historical_60d_min_low = df_single['low'].iloc[-71:-11].min()
    
    # 判定 A: 過去 10 天內，最低價必須「曾經跌破」之前的 60 日歷史低點（誘空洗盤）
    past_min_low = past_10d_window['low'].min()
    has_washout_drop = past_min_low <= historical_60d_min_low
    
    # 判定 B: 找出破底洗盤那天，成交量必須呈現「窒息量」（主力沒跑，散戶恐慌拋售）
    washout_day_idx = past_10d_window['low'].idxmin()
    washout_day_volume = past_10d_window.loc[washout_day_idx, 'volume']
    is_washout_volume_low = washout_day_volume < df_single['MA20_volume'].loc[washout_day_idx] * 0.8
    
    if not (has_washout_drop and is_washout_volume_low):
        return False, {"策略狀態": "觀測期未見惡意洗盤（未創60日新低或未見窒息量）"}

    # =========================================================================
    # 核心條件三：今日總攻判定（全面復活）
    # =========================================================================
    # 條件 A: 今日收盤價一舉創下過去 20 日的新高
    max_price_20d = df_single['close'].iloc[-21:-1].max()
    is_price_breakout_20d = today['close'] >= max_price_20d
    
    # 條件 B: 今日收盤必須是實體紅K (收盤價高於開盤價)
    is_today_positive = today['close'] > today['open']
    
    # 條件 C: 主力發動爆量點火 (今日成交量大於 5 日均量的 1.5 倍)
    is_volume_signal_up = today['volume'] >= today_ma5_vol * 1.5
    
    # 分流判斷：如果洗盤訊號已備，但今日動能未達標
    if not is_price_breakout_20d:
        return False, {"策略狀態": "進入潛伏觀測區（已惡意洗盤，但今日股價未創20日新高）"}
        
    if not (is_today_positive and is_volume_signal_up):
        return False, {"策略狀態": "進入潛伏觀測區（已惡意洗盤、股價突破，但今日紅K未爆量）"}
        
    # =========================================================================
    # 🎯 觸發成功：打包回傳數據（完美對接 hit_row.update）
    # =========================================================================
    if is_price_breakout_20d and is_today_positive and is_volume_signal_up:
        
        # 計算實戰所需的關鍵價量參考值
        today_change = round(((today['close'] - today['open']) / today['open']) * 100, 2)
        stop_loss_price = round(past_min_low * 0.99, 2)
        stop_loss_pct = round(((stop_loss_price - today['close']) / today['close']) * 100, 2)
        
        detail_info = {
            "策略狀態": "完全觸發（帶量紅K破底翻）",
            "今日收盤": today['close'],
            "今日K線漲幅": f"{today_change}%",
            "洗盤區最低價": past_min_low,
            "建議保命停損價": stop_loss_price,
            "預估停損幅度": f"{stop_loss_pct}%",
            "進場時年線斜率": f"{round(ma240_slope_5d * 100, 2)}%"
        }
        return True, detail_info
        
    return False, {"策略狀態": "未知異常狀態"}

# ==============================================================================
# 💡 策略邏輯備忘註腳 (Strategy Footnotes & Design Philosophy)
# ==============================================================================
# 1. 核心哲學：本策略專門捕捉「U 型底」或「地下室破冰」的轉骨黑馬股。
# 2. 徹底揚棄「前波高點」的時空猜測，改用中長線均線的「絕對乖離度」作為空間防守依據。
# 3. 承認並解鎖「價量時差 (Time Lag)」：
#    - 主力往往在底部最絕望、均線仍下彎時敲進「定海神針」的大量 (此時型態不符)。
#    - 隨後溫和量縮橫盤，等到季線轉強、年線減速時，當天成交量通常已趨於平淡 (此時無大量)。
#    - 因此，本策略引進「時空記憶體」，只要過去 20 天(一個月)曾有主力爆量足跡，
#      搭配「今日」價格與均線結構正式到位，即視為完美的波段買點。
# ==============================================================================

def st_bottom_u_turn_with_memory(df_single):
    """
    ***st_bottom_u_turn 策略 A-5：解鎖價量時差的「主力痕跡記憶系統」***
    
    【核心邏輯優化】
    - 拋棄「爆量與均線必須在同一天」的死板限制。
    - 記憶濾網：過去 20 天內曾出現過 > 20日均量 2.0 倍的紅K爆量，程式會記住此主力腳印。
    - 收網觸發：今日剛好走到「季線探頭、年線減速、價格創 60 日新高」的翻揚臨界點，立刻觸發。
    
    - 比st_bottom_u_turn_with_memory_20260711_01增加扣抵值濾網
    """
    if df_single.empty or len(df_single) < 250:
        return False, {}

    # --- 1. 計算基本技術指標 ---
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 流動性基本防禦
    if today['Vol_MA20'] < 300:
        return False, {}

    # --- 2. 主力爆量記憶體 (解鎖價量時差) ---
    # 計算每一天是否「成交量 >= 20日均量的 2.0 倍 且 當天收紅K」
    df_single['is_volume_burst'] = (df_single['Trading_Volume'] >= df_single['Vol_MA20'] * 2.0) & (df_single['close'] > df_single['open'])
    
    # 檢查「過去 20 個交易日（約一個月）」內，有沒有任何一天觸發過爆量
    has_volume_memory_20d = df_single['is_volume_burst'].rolling(20).max().iloc[-1] == 1.0

    # --- 3. 空間防守：季線在年線下方至少 8% 之外 (絕對低檔位階，免用前波高點) ---
    ma_gap_ratio = today['MA60'] / today['MA240'] if today['MA240'] > 0 else 1.0
    is_deep_enough = ma_gap_ratio <= 0.92  
    
    # --- 4. 價格實質突破：創 60 日（一季）最高收盤價，突破碗底頸線 ---
    max_close_60d = df_single['close'].iloc[-61:-1].max()
    is_price_breakout = today['close'] > max_close_60d
    
    # --- 5. 趨勢轉折與年線減速 (今天收網的技術條件) ---
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago != 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.015
    
    # 今日基本動能：不求今天暴巨量，但今天至少要是個多頭前進的收紅盤
    is_today_positive = today['close'] >= yesterday['close']

    # === 新增：年線扣抵值防禦濾網 ===
    # 找出 240 天前的股價（即今日 MA240 的扣抵位置）
    # 為了防止高價股高檔套牢壓力，未來 20 天的扣抵值（240天前~220天前）也必須納入考量
    ref_idx_240 = -240
    ref_idx_220 = -220
    
    if len(df_single) >= 240:
        price_240d_ago = df_single['close'].iloc[ref_idx_240]
        # 未來一個月內會扣抵到的最高價
        max_charge_price_next_month = df_single['close'].iloc[ref_idx_240:ref_idx_220].max()
        
        # 【核心防禦條件】: 今日股價如果距離未來一個月要扣抵的最高價「太遠」（例如跌幅超過 40%）
        # 代表一年前的今天是一座高不可攀的大山，年線在未來一個月「絕對不可能扣平」，只會加速下墜！
        is_charge_safe = today['close'] >= (max_charge_price_next_month * 0.55) # 至少要在扣抵最高價的 55% 以上
    else:
        is_charge_safe = False

    # === 結合原本的判定 ===
    is_hit = (has_volume_memory_20d and is_deep_enough and is_price_breakout and 
              is_ma60_turning_up and is_ma240_stable and is_today_positive and
              is_charge_safe) # 🌟 只有扣抵安全才准觸發
              
    # 找出過去 20 天最高的那次量能倍數，方便在 log 中觀察主力力道
    df_single['vol_ratio_track'] = df_single['Trading_Volume'] / df_single['Vol_MA20']
    max_vol_ratio_20d = df_single['vol_ratio_track'].rolling(20).max().iloc[-1]

    info = {
        "收盤": today['close'],
        "季線/年線比": f"{round(ma_gap_ratio * 100, 2)}%",
        "突破60日高點": is_price_breakout,
        "過去一個月有主力訊號": "有" if has_volume_memory_20d else "無",
        "期間最大主力波段量": f"{round(max_vol_ratio_20d, 2)}x",
        "今日量比20MA": f"{round(today['Trading_Volume'] / today['Vol_MA20'], 2)}x",
        "策略狀態": "【時差解鎖】主力潛伏完畢，今日結構正式轉強！" if is_hit else "未觸發"
    }
    
    return is_hit, info


def st_bottom_u_turn_with_memory_20260711_01(df_single):
    """
    ***st_bottom_u_turn 策略 A-5：解鎖價量時差的「主力痕跡記憶系統」***
    
    【核心邏輯優化】
    - 拋棄「爆量與均線必須在同一天」的死板限制。
    - 記憶濾網：過去 20 天內曾出現過 > 20日均量 2.0 倍的紅K爆量，程式會記住此主力腳印。
    - 收網觸發：今日剛好走到「季線探頭、年線減速、價格創 60 日新高」的翻揚臨界點，立刻觸發。
    無扣抵值濾網
    """
    if df_single.empty or len(df_single) < 250:
        return False, {}

    # --- 1. 計算基本技術指標 ---
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 流動性基本防禦
    if today['Vol_MA20'] < 300:
        return False, {}

    # --- 2. 主力爆量記憶體 (解鎖價量時差) ---
    # 計算每一天是否「成交量 >= 20日均量的 2.0 倍 且 當天收紅K」
    df_single['is_volume_burst'] = (df_single['Trading_Volume'] >= df_single['Vol_MA20'] * 2.0) & (df_single['close'] > df_single['open'])
    
    # 檢查「過去 20 個交易日（約一個月）」內，有沒有任何一天觸發過爆量
    has_volume_memory_20d = df_single['is_volume_burst'].rolling(20).max().iloc[-1] == 1.0

    # --- 3. 空間防守：季線在年線下方至少 8% 之外 (絕對低檔位階，免用前波高點) ---
    ma_gap_ratio = today['MA60'] / today['MA240'] if today['MA240'] > 0 else 1.0
    is_deep_enough = ma_gap_ratio <= 0.92  
    
    # --- 4. 價格實質突破：創 60 日（一季）最高收盤價，突破碗底頸線 ---
    max_close_60d = df_single['close'].iloc[-61:-1].max()
    is_price_breakout = today['close'] > max_close_60d
    
    # --- 5. 趨勢轉折與年線減速 (今天收網的技術條件) ---
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago != 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.015
    
    # 今日基本動能：不求今天暴巨量，但今天至少要是個多頭前進的收紅盤
    is_today_positive = today['close'] >= yesterday['close']
    
    # --- 6. 綜合判定 ---
    is_hit = (has_volume_memory_20d and is_deep_enough and is_price_breakout and 
              is_ma60_turning_up and is_ma240_stable and is_today_positive)
              
    # 找出過去 20 天最高的那次量能倍數，方便在 log 中觀察主力力道
    df_single['vol_ratio_track'] = df_single['Trading_Volume'] / df_single['Vol_MA20']
    max_vol_ratio_20d = df_single['vol_ratio_track'].rolling(20).max().iloc[-1]

    info = {
        "收盤": today['close'],
        "季線/年線比": f"{round(ma_gap_ratio * 100, 2)}%",
        "突破60日高點": is_price_breakout,
        "過去一個月有主力訊號": "有" if has_volume_memory_20d else "無",
        "期間最大主力波段量": f"{round(max_vol_ratio_20d, 2)}x",
        "今日量比20MA": f"{round(today['Trading_Volume'] / today['Vol_MA20'], 2)}x",
        "策略狀態": "【時差解鎖】主力潛伏完畢，今日結構正式轉強！" if is_hit else "未觸發"
    }
    
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
