import pandas as pd
import numpy as np

from monitor.config import DEBUG_VERBOSE

# ==========================================
# 錢塘潮 11 大防禦賣訊
# ==========================================

DEBUG_VERBOSE = True


def mon_qiantang_yi_zhu_qing_xiang(df_single: pd.DataFrame, profile: dict):
    """一柱清香 (高檔爆量長上影)
    
    公式邏輯
    ((最高/收盤) ≧ 1.03 and 劵餘 > 0) and (2天最大值 = 9天最高最大值  且 2天最高成交量 = 9天成交量大值) 且 成交量 ≧ 4000
    """

    
    if len(df_single) < 20: return False, {}
    today = df_single.iloc[-1]
    
    if today.get('Trading_Volume', 0) < profile.get('min_vol', 1000):
        return False, {}
        
    high, low, close, open_p = today['max'], today['min'], today['close'], today['open']
    total_range = high - low
    if total_range == 0: return False, {}
    
    upper_shadow = high - max(open_p, close)
    is_high_shadow = (upper_shadow / total_range) >= 0.50
    vol_ma5 = df_single['Trading_Volume'].iloc[-6:-1].mean()
    is_vol_burst = today['Trading_Volume'] > (vol_ma5 * 2.0)
    
    is_hit = is_high_shadow and is_vol_burst
    info = {
        '轉空賣訊': '一柱清香',
        '操作建議': '創高爆量長上影，主力高檔拉高出貨，建議減碼或停利離場。'
    } if is_hit else {}
    
    return is_hit, info


def mon_qiantang_dang_tou_bang_he(df_single: pd.DataFrame, profile: dict):
    """當頭棒喝 (創高長黑K/吞噬)"""
    if len(df_single) < 20: return False, {}
    today, prev = df_single.iloc[-1], df_single.iloc[-2]
    
    if today.get('Trading_Volume', 0) < profile.get('min_vol', 1000):
        return False, {}

    is_black_k = today['close'] < today['open']
    is_engulf = (today['open'] >= prev['close']) and (today['close'] < prev['min'])
    is_high_vol = today['Trading_Volume'] > df_single['Trading_Volume'].iloc[-6:-1].mean() * 1.5
    
    is_hit = is_black_k and is_engulf and is_high_vol
    info = {
        '轉空賣訊': '當頭棒喝',
        '操作建議': '高檔巨量長黑吞噬 K 線，多頭力竭，極易形成中期頭部，建議避險。'
    } if is_hit else {}
    
    return is_hit, info

def mon_qiantang_xia_shan_meng_hu(df_single: pd.DataFrame, profile: dict):
    """下山猛虎 (爆量跌破關鍵均線)"""
    if len(df_single) < 20: return False, {}
    today = df_single.iloc[-1]
    
    ma20 = df_single['close'].iloc[-20:].mean()
    is_break_ma20 = (df_single['close'].iloc[-2] >= ma20) and (today['close'] < ma20)
    is_heavy_vol = today.get('Trading_Volume', 0) > profile.get('min_vol', 1000)
    
    is_hit = is_break_ma20 and is_heavy_vol
    info = {
        '轉空賣訊': '下山猛虎',
        '操作建議': '帶量長黑跌破月線(20MA)，趨勢正式轉空，建議順勢止損離場。'
    } if is_hit else {}
    
    return is_hit, info

def mon_qiantang_he_shi(df_single: pd.DataFrame):
    """合十 (短天期均線死亡交叉)"""
    if len(df_single) < 20: return False, {}
    
    ma5 = df_single['close'].rolling(5).mean()
    ma20 = df_single['close'].rolling(20).mean()
    
    is_hit = (ma5.iloc[-2] >= ma20.iloc[-2]) and (ma5.iloc[-1] < ma20.iloc[-1])
    info = {
        '轉空賣訊': '合十',
        '操作建議': '5日均線下穿20日均線形成死叉，短線波段轉弱，注意下行風險。'
    } if is_hit else {}
    
    return is_hit, info


import pandas as pd


def mon_qiantang_jiang_long_fu_hu(df_single: pd.DataFrame):
    """降龍伏虎 (跳空開低大黑K)"""
    if len(df_single) < 5: return False, {}
    today, prev = df_single.iloc[-1], df_single.iloc[-2]
    
    is_gap_down = today['open'] < (prev['close'] * 0.985)
    is_black_k = (today['open'] - today['close']) / today['open'] > 0.02
    
    is_hit = is_gap_down and is_black_k
    info = {
        '轉空賣訊': '降龍伏虎',
        '操作建議': '出現向下跳空長黑 K 線，多頭防線全面失守，空方力道強勁。'
    } if is_hit else {}
    
    return is_hit, info


def mon_qiantang_qing_song_xian_zhuan_kong(df_single: pd.DataFrame):
    """輕鬆線轉空, 月下老人 (輕鬆線死亡交叉)"""
    if 'easy_b' not in df_single.columns or 'easy_s' not in df_single.columns:
        return False, {}
        
    easy_b, easy_s = df_single['easy_b'], df_single['easy_s']
    is_hit = (easy_b.iloc[-2] >= easy_s.iloc[-2]) and (easy_b.iloc[-1] < easy_s.iloc[-1])
    
    info = {
        '轉空賣訊': '輕鬆線轉空',
        '操作建議': '輕鬆線指標由多轉空，長線趨勢走弱，防守位宜提高。'
    } if is_hit else {}
    
    return is_hit, info


def mon_qiantang_kd_dead_cross(df_single: pd.DataFrame):
    """KD高檔死叉, 這是地底穿心嗎?  (過熱區死亡交叉)"""
    if 'K' not in df_single.columns or 'D' not in df_single.columns:
        return False, {}
        
    k, d = df_single['K'], df_single['D']
    is_high = k.iloc[-2] > 75
    is_dead_cross = (k.iloc[-2] >= d.iloc[-2]) and (k.iloc[-1] < d.iloc[-1])
    
    is_hit = is_high and is_dead_cross
    info = {
        '轉空賣訊': 'KD高檔死叉',
        '操作建議': 'KD 指標高檔過熱區出現死亡交叉，短線修正壓力大。'
    } if is_hit else {}
    
    return is_hit, info


def mon_qiantang_da_zhong_xia_ke(df_single: pd.DataFrame, profile: dict = None, verbose: bool = DEBUG_VERBOSE):
    """打鐘下課 (主力法人大賣/反彈逢下彎均線)

    核心邏輯：
    1. 收盤價 > 輕鬆線 (easy_line)
    2. 今日輕鬆線 < 1天前輕鬆線 (輕鬆線下彎)
    3. 家數差 <= -30 (籌碼鬆動/散戶買進賣方集中)
    4. 外資買賣超 <= major_sell 門檻 且 主力買賣超 <= major_sell 門檻
    """
    profile = profile or {}

    if len(df_single) < 5:
        print("  ⚠️ [打鐘下課] K線資料不足 5 筆，跳過檢測")
        return False, {}

    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    close = today['close']

    # --- 1. 技術面參數讀取 ---
    easy_line_today = today.get('easy_line', None)
    easy_line_yesterday = yesterday.get('easy_line', None)

    if easy_line_today is None or easy_line_yesterday is None:
        print("  ⚠️ [打鐘下課] 缺少 easy_line 技術指標欄位，無法計算")
        return False, {}

    cond1_above_easy = close > easy_line_today
    cond2_easy_down = easy_line_today < easy_line_yesterday

    # --- 2. 籌碼面 Profile 門檻與動態微調計算 ---
    base_major_sell = profile.get('major_sell', -800)
    profile_category = profile.get('category', 'default')

    # 高價 IC 設計股動態調降張數門檻
    major_sell_limit = base_major_sell
    if profile_category == 'ic_design':
        if close >= 1000:
            major_sell_limit = max(base_major_sell, -150)
        elif close >= 500:
            major_sell_limit = max(base_major_sell, -300)

    # --- 3. 籌碼面數據讀取 ---
    broker_diff = today.get('broker_diff', 0) if 'broker_diff' in df_single.columns else 0
    foreign_net = today.get('foreign_net', 0) if 'foreign_net' in df_single.columns else 0
    major_net = today.get('major_net', 0) if 'major_net' in df_single.columns else 0

    cond3_broker_diff = broker_diff <= -30 if 'broker_diff' in df_single.columns else True
    cond4_foreign_sell = foreign_net <= major_sell_limit
    cond5_major_sell = major_net <= major_sell_limit

    # 綜合判斷結果
    is_hit = (
        cond1_above_easy and 
        cond2_easy_down and 
        cond3_broker_diff and 
        cond4_foreign_sell and 
        cond5_major_sell
    )

    # --- 🔍 參數細節詳細列印 Debug 區塊 ---
    # 7. 🔔 詳細數據輸出區塊 (受到 verbose 開關控制)
    if verbose:
        print(f"\n  🔍 === [打鐘下課 參數檢查儀表板] ===")
        print(f"  • 套用族群 Profile  : {profile_category} (原始 major_sell: {base_major_sell})")
        print(f"  • 動態賣超張數門檻 : <= {major_sell_limit} 張")
        print(f"  • 今日收盤 / 輕鬆線 : 收盤 ${close:.2f} | 今日輕鬆線 ${easy_line_today:.2f} | 昨日輕鬆線 ${easy_line_yesterday:.2f}")
        print(f"  • 籌碼數據現況     : 外資買賣超 {foreign_net} 張 | 主力買賣超 {major_net} 張 | 家數差 {broker_diff}")
        print(f"  • 條件 1 (站上輕鬆線): {cond1_above_easy} ({'PASS' if cond1_above_easy else 'FAIL'})")
        print(f"  • 條件 2 (輕鬆線下彎): {cond2_easy_down} ({'PASS' if cond2_easy_down else 'FAIL'})")
        print(f"  • 條件 3 (家數差<=-30): {cond3_broker_diff} ({'PASS' if cond3_broker_diff else 'FAIL'})")
        print(f"  • 條件 4 (外資大賣)  : {cond4_foreign_sell} ({'PASS' if cond4_foreign_sell else 'FAIL'} -> {foreign_net} <= {major_sell_limit})")
        print(f"  • 條件 5 (主力大賣)  : {cond5_major_sell} ({'PASS' if cond5_major_sell else 'FAIL'} -> {major_net} <= {major_sell_limit})")
        print(f"  👉 最終觸發結果     : {'🚨 觸發賣訊' if is_hit else '✅ 安全過關'}\n")

    info = {
        '轉空賣訊': '打鐘下課',
        '操作建議': f'股價反彈至下彎輕鬆線上方，但主力與外資單日出現巨量拋售(賣超門檻 {abs(major_sell_limit)} 張)且籌碼趨向分散，逢反彈宜儘速退場避險。'
    } if is_hit else {}

    return is_hit, info

def mon_qiantang_tian_nv_san_hua(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """天女散花

    公式 logic:
    1. 當日最高 == 近 10 天最高價 (含當日)
    2. 當日成交量 == 近 10 天成交量最大值 (含當日)
    3. 當日成交量 >= 最低流動性門檻 (預設 3000 張，高價股自動微調)
    4. 當日最高 / 1天前收盤 > 1.065
    5. 當日最高 / 當日收盤 >= 1.01
    6. 當日融券餘額 > 0
    """
    
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    if len(df_single) < 10:
        if verbose:
            print(f"❌ [天女散花] 資料筆數不足 10 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    c_1 = df_single['close'].iloc[-2]  # 前一日收盤價

    # 📍 呼叫動態門檻函數 (錢塘潮防止買到成交量過低的股票原始基準門檻：3000 張)
    min_vol_shares = get_qiantang_min_volume_shares(
        price=today['close'],
        profile=profile
    )

    # 提取指標數值
    max_10d = df_single['max'].iloc[-10:].max()
    vol_10d = df_single['Trading_Volume'].iloc[-10:].max()

    v_0 = today['Trading_Volume']
    surge_ratio = today['max'] / c_1 if (is_valid(c_1) and c_1 > 0) else 0
    high_close_ratio = today['max'] / today['close'] if (is_valid(today['close']) and today['close'] > 0) else 0
    short_balance = today.get('ShortSaleTodayBalance', None)

    # 條件邏輯判斷
    cond1_max_price = (today['max'] == max_10d)
    cond2_max_vol = (v_0 == vol_10d)
    cond3_min_vol = (v_0 >= min_vol_shares)  # 自動對齊高價股門檻 (單位：股)
    cond4_surge = (surge_ratio > 1.065)
    cond5_high_close_ratio = (high_close_ratio >= 1.02)
    
    if is_valid(short_balance) and 'ShortSaleTodayBalance' in df_single.columns:
        cond6_short_balance = (short_balance > 0)
        has_short_col = True
    else:
        cond6_short_balance = True
        has_short_col = False

    is_hit = (
        cond1_max_price and cond2_max_vol and cond3_min_vol and 
        cond4_surge and cond5_high_close_ratio and cond6_short_balance
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        min_vol_lots = min_vol_shares / 1000.0

        print("\n" + "=" * 55)
        print(f"🔔 [天女散花] 股票: {stock_id} | 日期: {date_str} | 適用門檻: {min_vol_lots:,.0f} 張")
        print("-" * 55)
        print(f" [{ '✓' if cond1_max_price else '✕' }] 1. 最高等於10日最高 : 最高價 {today['max']:.2f} == 10日最高 {max_10d:.2f}")
        print(f" [{ '✓' if cond2_max_vol else '✕' }] 2. 成交量等於10日天量 : 當日量 {v_0/1000:,.0f} 張 == 10日最大 {vol_10d/1000:,.0f} 張")
        print(f" [{ '✓' if cond3_min_vol else '✕' }] 3. 達最低流動性門檻 : 當日量 {v_0/1000:,.0f} 張 >= 門檻 {min_vol_lots:,.0f} 張")
        print(f" [{ '✓' if cond4_surge else '✕' }] 4. 最高/1天前收盤 > 1.065 : 幅度 {surge_ratio:.3f} > 1.065 (+6.5%)")
        print(f" [{ '✓' if cond5_high_close_ratio else '✕' }] 5. 最高/收盤 ≧ 1.02   : 比例 {high_close_ratio:.3f} >= 1.020")
        
        if has_short_col:
            print(f" [{ '✓' if cond6_short_balance else '✕' }] 6. 融券餘額 > 0       : 當日融券餘額 {short_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 6. 融券餘額 > 0       : 無欄位資料 (預設通過)")
            
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發天女散花]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '天女散花',
        '操作建議': f'當日創10日新高且爆出10日天量({v_0 // 1000:,.0f} 張)，衝高後滯漲留上影線，代表高檔換手失敗且主力籌碼鬆動，建議停利離場。'
    } if is_hit else {}

    return is_hit, info

def mon_qiantang_ming_ri_huang_hua(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """明日黃花 (創高爆量滯漲) - FinMind 最新版欄位專用

    核心邏輯：
    1. 2天前急衝大漲 ≧ 6.5% * surge_mult (依族群波動度動態微調暴衝門檻)
    2. 1天前高檔震盪或續強 (c_1 >= c_2)
    3. 今日收盤跌破2天前收盤 (c_0 < c_2)
    4. 2天前成交量 ≧ 最低流動性門檻 (profile 指定 min_vol，單位為「股」)
    5. 2天前成交量為近 21 天(含當日)的最大量 (頂部天量換手)
    6. 融券餘額 (ShortSaleTodayBalance) > 0
    """
    profile = profile or {}

    # 輔助函式：檢查是否為有效數值 (非 None 且非 NaN)
    def is_valid(val):
        return val is not None and pd.notna(val)

    # 至少需要 24 筆歷史資料以支援 21 天天量視窗計算 (iloc[-23:-2] 包含當天共 21 天)
    if len(df_single) < 24:
        if verbose:
            print(f"❌ [明日黃花] 資料筆數不足 24 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    day_1 = df_single.iloc[-2]
    day_2 = df_single.iloc[-3]
    day_3 = df_single.iloc[-4]

    # --- 1. 提取價格與成交量數據 (單位：股) ---
    c_0 = today.get('close', None)
    c_1 = day_1.get('close', None)
    c_2 = day_2.get('close', None)
    c_3 = day_3.get('close', None)

    v_2 = day_2.get('Trading_Volume', None)

    # --- 2. 從 Profile 讀取族群基礎參數 (單位：股，預設 1,000 張 = 1,000,000 股) ---
    base_min_vol = profile.get('min_vol', 1000 * 1000)
    surge_mult = profile.get('surge_mult', 1.0)
    profile_name = profile.get('name', '')

    # 動態調整最低成交量門檻 (單位：股)
    min_vol = base_min_vol
    if is_valid(c_2):
        if 'ic' in profile_name.lower() or 'IC設計' in profile_name or profile.get('category') == 'ic_design':
            if c_2 >= 1000:
                min_vol = min(base_min_vol, 300 * 1000)    # 千金股：防線下修至 300 張
            elif c_2 >= 500:
                min_vol = min(base_min_vol, 500 * 1000)    # 高價股：防線下修至 500 張

    # 計算動態大漲門檻
    target_surge_ratio = 1.0 + (0.065 * surge_mult)
    actual_surge_ratio = (c_2 / c_3) if (is_valid(c_2) and is_valid(c_3) and c_3 > 0) else None

    # --- 3. 條件邏輯判斷 ---
    # 條件 1：2天前急衝大漲
    cond1 = (actual_surge_ratio >= target_surge_ratio) if is_valid(actual_surge_ratio) else False

    # 條件 2：1天前高檔震盪或續強
    cond2 = (c_1 >= c_2) if (is_valid(c_1) and is_valid(c_2)) else False

    # 條件 3：今日收盤跌破 2天前收盤
    cond3 = (c_0 < c_2) if (is_valid(c_0) and is_valid(c_2)) else False

    # 條件 4：最低成交量門檻 (股數對比)
    cond4_min_vol = (v_2 >= min_vol) if is_valid(v_2) else False

    # 條件 5：近 21 天最大量 (含 2 天前當天，共 21 個交易日：iloc[-23:-2])
    v_21_series = df_single['Trading_Volume'].iloc[-23:-2]
    v_21_max = v_21_series.max() if not v_21_series.empty else None
    cond5_max_vol = (v_2 >= v_21_max) if (is_valid(v_2) and is_valid(v_21_max)) else False

    # 條件 6：融券餘額 (FinMind: ShortSaleTodayBalance) > 0
    short_val = today.get('ShortSaleTodayBalance', None)

    if is_valid(short_val):
        cond6_short_balance = short_val > 0
        has_short_col = True
    else:
        cond6_short_balance = True  # 若未合併信用交易 DataFrame 或缺失時預設通過
        has_short_col = False

    # 綜合評估
    is_hit = cond1 and cond2 and cond3 and cond4_min_vol and cond5_max_vol and cond6_short_balance

    # --- 4. 🔔 詳細數據輸出區塊 (顯示時轉換為張數) ---
    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        print("\n" + "=" * 55)
        print(f"🔔 [明日黃花 訊號檢測分析] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)

        surge_pct_str = f"{(actual_surge_ratio - 1) * 100:.2f}%" if is_valid(actual_surge_ratio) else "N/A"
        target_pct_str = f"{(target_surge_ratio - 1) * 100:.2f}%"
        print(f" [{ '✓' if cond1 else '✕' }] 1. 2天前爆衝大漲 : {surge_pct_str} (>= 門檻 {target_pct_str})")

        c1_str = f"{c_1:.2f}" if is_valid(c_1) else "N/A"
        c2_str = f"{c_2:.2f}" if is_valid(c_2) else "N/A"
        print(f" [{ '✓' if cond2 else '✕' }] 2. 1天前高檔撐住 : 1天前收盤 {c1_str} >= 2天前收盤 {c2_str}")

        c0_str = f"{c_0:.2f}" if is_valid(c_0) else "N/A"
        print(f" [{ '✓' if cond3 else '✕' }] 3. 今日跌破爆量日 : 今日收盤 {c0_str} < 2天前收盤 {c2_str}")

        v2_lots_str = f"{v_2 / 1000.0:,.0f} 張" if is_valid(v_2) else "N/A"
        min_vol_lots_str = f"{min_vol / 1000.0:,.0f} 張"
        print(f" [{ '✓' if cond4_min_vol else '✕' }] 4. 流動性門檻   : 2天前成交量 {v2_lots_str} (>= {min_vol_lots_str})")

        v21_max_lots_str = f"{v_21_max / 1000.0:,.0f} 張" if is_valid(v_21_max) else "N/A"
        print(f" [{ '✓' if cond5_max_vol else '✕' }] 5. 創近21天天量 : 2天前量 {v2_lots_str} >= 近21天最大量 {v21_max_lots_str}")

        if has_short_col:
            short_str = f"{short_val:,.0f} 張"
            print(f" [{ '✓' if cond6_short_balance else '✕' }] 6. 融券餘額條件 : 目前融券餘額 {short_str} (> 0)")
        else:
            print(f" [✓] 6. 融券餘額條件 : 無融券資料 (預設通過)")

        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發明日黃花]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    # --- 5. Info 輸出準備 ---
    v2_print_lots = f"{v_2 // 1000:,.0f}" if is_valid(v_2) else "0"
    min_vol_print_lots = f"{int(min_vol // 1000):,.0f}"
    c2_print = f"{c_2:.0f}" if is_valid(c_2) else "N/A"

    info = {
        '轉空賣訊': '明日黃花',
        '操作建議': f'2天前爆出近21天天量({v2_print_lots} 張，股價約 {c2_print} 元，套用門檻 {min_vol_print_lots} 張)並創高後滯漲，今日跌破爆量當天收盤，主力換手失敗且大量套牢賣壓形成，建議注意轉空風險離場。'
    } if is_hit else {}

    return is_hit, info

def mon_qiantang_ming_ri_huang_hua_old(df_single: pd.DataFrame, profile: dict = None):
    """明日黃花 (創高爆量滯漲)

    核心邏輯：
    1. 2天前大漲 ≧ 6.5% * surge_mult (依族群波動度動態微調暴衝門檻) 且
    2. 1天前高檔震盪或續強 (c_1 >= c_2) 且
    3. 今日收盤跌破2天前收盤 (c_0 < c_2) 且
    4. 2天前成交量 ≧ 最低流動性門檻 (由 profile 指定 min_vol，IC設計高價股按股價階梯自動微調) 且
    5. 2天前成交量為近 21 天(含當日)的最大量 (頂部天量換手) 且
    6. 融券餘額 > 0 <--- 這個欄位有沒有資料待確定
    """
    profile = profile or {}
    
    # 至少需要 24 筆歷史資料以支援 21 天天量視窗計算 (iloc[-23:-2])
    if len(df_single) < 24:
        return False, {}

    # 1. 價格位置點 (-1: 今日, -2: 1天前, -3: 2天前, -4: 3天前)
    c_0 = df_single['close'].iloc[-1]
    c_1 = df_single['close'].iloc[-2]
    c_2 = df_single['close'].iloc[-3]
    c_3 = df_single['close'].iloc[-4]

    # 2. 2天前成交量
    v_2 = df_single['Trading_Volume'].iloc[-3]

    # 3. 從 Profile 讀取族群基礎參數
    base_min_vol = profile.get('min_vol', 1000)
    surge_mult = profile.get('surge_mult', 1.0)
    profile_name = profile.get('name', '')

    # 4. 最低成交量門檻微調 (針對 IC 設計 / 高波動族群，依爆量當日股價下修門檻)
    min_vol = base_min_vol
    if 'ic' in profile_name.lower() or 'IC設計' in profile_name or profile.get('category') == 'ic_design':
        if c_2 >= 1000:
            min_vol = min(base_min_vol, 300)   # 千金股：防線下修至 300 張
        elif c_2 >= 500:
            min_vol = min(base_min_vol, 500)   # 高價股：防線下修至 500 張

    # 5. 計算動態大漲門檻 (基準 6.5% 乘以族群波動係數)
    target_surge_ratio = 1.0 + (0.065 * surge_mult)

    # --- 條件邏輯判斷 ---
    # 條件 1：2天前急衝大漲 (依族群波動度調整門檻)
    cond1 = (c_2 / c_3) >= target_surge_ratio

    # 條件 2：1天前高檔震盪或續強
    cond2 = c_1 >= c_2

    # 條件 3：今日收盤跌破 2天前收盤
    cond3 = c_0 < c_2

    # 條件 4：最低成交量門檻
    cond4_min_vol = v_2 >= min_vol

    # 條件 5：近 21 天最大量 (頂部天量，取 iloc[-23:-2] 排除今日與昨日)
    v_21_max = df_single['Trading_Volume'].iloc[-23:-2].max()
    cond5_max_vol = v_2 >= v_21_max

    # 條件 6：融券餘額 > 0
    cond6_short_balance = df_single['Margin_Short_Balance'].iloc[-1] > 0 if 'Margin_Short_Balance' in df_single.columns else True

    # 綜合評估
    is_hit = cond1 and cond2 and cond3 and cond4_min_vol and cond5_max_vol and cond6_short_balance

    info = {
        '轉空賣訊': '明日黃花',
        '操作建議': f'2天前爆出近21天天量(當日股價約 {c_2:.0f} 元，套用門檻 {min_vol} 張)並創高後滯漲，今日跌破爆量當天收盤，主力換手失敗且大量套牢賣壓形成，建議注意轉空風險離場。'
    } if is_hit else {}

    return is_hit, info

def mon_qiantang_ni_diu_wo_jian(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """你丟我撿 (主力持續派發 / 散戶接盤) - FinMind 欄位專用版

    核心邏輯：
    1. 技術面（雙重確認）：
        - 輕鬆賣盤大於買盤 (B > A)，且 KD 處於高檔區 (K > 70) 或剛發生高檔死亡交叉。
        - 價格實質轉弱防護 (Price Weakness)：(當日收黑K 且 跌破前日低點) OR (收盤價跌破 5日線)。
    2. 籌碼面（高門檻派發）：
        - 有分點資料：(主力賣超 >= 動態門檻 AND 外資賣超 >= 動態門檻) OR (分點買賣家數差 >= 家數差門檻)
        - 無分點資料 (Fallback)：主力大賣 + 外資大賣 + 投信無護盤(<=0)，達成雙法人同步派發驗證。
    """
    profile = profile or {}

    # 至少需要 5 筆歷史資料（計算 5MA 與 前日 K線 需要）
    if len(df_single) < 5:
        if verbose:
            print(f"❌ [你丟我撿] 資料筆數不足 5 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    prev_day = df_single.iloc[-2]  # 用於判斷前日低點與 KD 死亡交叉

    # 輔助函式：檢查是否為有效數值 (非 None 且非 NaN)
    def is_valid(val):
        return val is not None and pd.notna(val)

    # --- 1. 動態計算籌碼賣超門檻 (單位：股) ---
    volume = today.get('Trading_Volume', None)  # 總成交股數

    # 從 Profile 讀取比例門檻與保底股數 (預設 30萬股 = 300張)
    major_ratio = profile.get('major_sell_ratio', 0.05)     # 預設主力賣超佔總成交量 >= 5%
    foreign_ratio = profile.get('foreign_sell_ratio', 0.05) # 預設外資賣超佔總成交量 >= 5%
    min_sell_shares = profile.get('min_sell_shares', 300 * 1000)  # 保底股數 (300張 * 1000 = 300,000股)

    # 賣超為負數，使用 -max(...) 算出動態上限股數
    if is_valid(volume) and volume > 0:
        major_sell_limit = -max(volume * major_ratio, min_sell_shares)
        foreign_sell_limit = -max(volume * foreign_ratio, min_sell_shares)
    else:
        major_sell_limit = -float(min_sell_shares)
        foreign_sell_limit = -float(min_sell_shares)

    broker_diff_limit = profile.get('broker_diff', 20)  # 家數差門檻 (正數：買家數 > 賣家數，散戶接盤)

    # --- 2. 提取技術面與籌碼面數據 (純 FinMind 欄位: 最低價使用 min) ---
    close_val = today.get('close', None)
    open_val  = today.get('open', None)
    low_val   = today.get('min', None)       # 直接指定 FinMind min 欄位
    prev_low  = prev_day.get('min', None)    # 直接指定 FinMind min 欄位

    # 計算 ma5, 抓取最後 5 筆 close 計算 5MA
    if len(df_single) >= 5:
        last_5_close = df_single['close'].iloc[-5:]
        # 只有當這 5 天「完全沒有 NaN」時才計算 5MA
        ma5_val = last_5_close.mean() if not last_5_close.isna().any() else None
    else:
        ma5_val = None

    easy_a = today.get('easy_buy', None)
    easy_b = today.get('easy_sell', None)
    
    k_val = today.get('K', None)
    d_val = today.get('D', None)
    prev_k = prev_day.get('K', None)
    prev_d = prev_day.get('D', None)

    major_net = today.get('major_net', None)      # 主力買賣超 (股)
    foreign_net = today.get('foreign_net', None)  # 外資買賣超 (股)
    trust_net = today.get('trust_net', None)      # 投信買賣超 (股)
    broker_diff = today.get('broker_diff', None)  # 家數差 (家)

    # --- 3. 條件邏輯判斷 ---

    # A. 技術面判斷 1：輕鬆賣盤與 KD 條件
    cond_easy = (easy_b > easy_a) if (is_valid(easy_a) and is_valid(easy_b)) else True

    cond_kd_overbought = (k_val > 70) if is_valid(k_val) else False
    cond_kd_death_cross = (prev_k > prev_d and k_val < d_val) if all(map(is_valid, [k_val, d_val, prev_k, prev_d])) else False
    cond_tech_kd = cond_kd_overbought or cond_kd_death_cross

    # B. 技術面判斷 2：價格實質轉弱防護（防範高檔強勢續噴）
    cond_black_k = (close_val < open_val) if (is_valid(close_val) and is_valid(open_val)) else False
    cond_break_prev_low = (low_val < prev_low) if (is_valid(low_val) and is_valid(prev_low)) else False
    cond_pattern_weak = cond_black_k and cond_break_prev_low

    cond_below_ma5 = (close_val < ma5_val) if (is_valid(close_val) and is_valid(ma5_val)) else False

    cond_price_weak = cond_pattern_weak or cond_below_ma5
    cond_tech = cond_easy and cond_tech_kd and cond_price_weak

    # C. 籌碼面判斷 (全股數條件比較)
    cond_chip_main = (major_net <= major_sell_limit) and (foreign_net <= foreign_sell_limit) if (is_valid(major_net) and is_valid(foreign_net)) else False

    if is_valid(broker_diff):
        cond_chip_broker = broker_diff >= broker_diff_limit
        chip_fallback_used = False
    else:
        is_trust_not_buying = (trust_net <= 0) if is_valid(trust_net) else True
        cond_chip_broker = cond_chip_main and is_trust_not_buying
        chip_fallback_used = True

    cond_chip = cond_chip_main or cond_chip_broker
    is_hit = cond_tech and cond_chip

    # --- 4. 🔔 詳細數據輸出區塊 (顯示時轉換為張數) ---
    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        print("\n" + "=" * 55)
        print(f"🔔 [你丟我撿 訊號檢測分析] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        
        easy_a_str = f"{easy_a:.1f}" if is_valid(easy_a) else "N/A"
        easy_b_str = f"{easy_b:.1f}" if is_valid(easy_b) else "N/A"
        print(f" [{ '✓' if cond_easy else '✕' }] 1. 輕鬆買賣指標 : B(賣) {easy_b_str} > A(買) {easy_a_str}")
        
        k_str = f"{k_val:.1f}" if is_valid(k_val) else "N/A"
        d_str = f"{d_val:.1f}" if is_valid(d_val) else "N/A"
        print(f" [{ '✓' if cond_tech_kd else '✕' }] 2. KD 高檔/死叉 : K值 {k_str} | D值 {d_str}")

        close_str = f"{close_val:.2f}" if is_valid(close_val) else "N/A"
        ma5_str   = f"{ma5_val:.2f}" if is_valid(ma5_val) else "N/A"
        prev_low_str = f"{prev_low:.2f}" if is_valid(prev_low) else "N/A"
        print(f" [{ '✓' if cond_price_weak else '✕' }] 3. 價格實質轉弱 : (黑K 且 破前低 {prev_low_str}) OR (收盤 {close_str} < 5MA {ma5_str})")

        # 顯示轉換：股數 / 1000 -> 張數
        maj_lots_str = f"{major_net / 1000.0:,.0f} 張" if is_valid(major_net) else "N/A"
        for_lots_str = f"{foreign_net / 1000.0:,.0f} 張" if is_valid(foreign_net) else "N/A"
        maj_limit_lots = major_sell_limit / 1000.0
        for_limit_lots = foreign_sell_limit / 1000.0

        print(f" [{ '✓' if cond_chip_main else '✕' }] 4. 法人賣超門檻 : 主力 {maj_lots_str} (<= {maj_limit_lots:,.0f}張) & 外資 {for_lots_str} (<= {for_limit_lots:,.0f}張) [佔比 {major_ratio*100:.0f}%]")

        if not chip_fallback_used:
            bd_str = f"{broker_diff:.0f}" if is_valid(broker_diff) else "N/A"
            print(f" [{ '✓' if cond_chip_broker else '✕' }] 5. 分點籌碼分散 : 買賣家數差 {bd_str} (>= {broker_diff_limit})")
        else:
            tru_lots_str = f"{trust_net / 1000.0:,.0f} 張" if is_valid(trust_net) else "N/A"
            print(f" [{ '✓' if cond_chip_broker else '✕' }] 5. 分點缺失(啟動備援): 外資+主力大賣 且 投信無護盤 ({tru_lots_str})")

        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發你丟我撿]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    # 安全地準備 Info 輸出 (股數 / 1000 換算為張數)
    maj_print = f"{major_net / 1000.0:,.0f}" if is_valid(major_net) else "0"
    for_print = f"{foreign_net / 1000.0:,.0f}" if is_valid(foreign_net) else "0"
    bd_print  = f"{broker_diff:.0f}" if is_valid(broker_diff) else "無資料"

    info = {
        '轉空賣訊': '你丟我撿',
        '操作建議': f'股價處於高檔且技術面實質轉弱（破前低或跌破5MA），籌碼呈現持續派發（主力 {maj_print} 張 / 外資 {for_print} 張，家數差 {bd_print}），呈現明顯散戶接盤格局，建議逢高減碼。'
    } if is_hit else {}

    return is_hit, info


def mon_qiantang_ni_diu_wo_jian_old(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """你丟我撿 (主力持續派發 / 散戶接盤)

    核心邏輯：
    1. 技術面：輕鬆賣盤大於買盤 (B > A)，且 KD 處於高檔區 (K > 70) 或剛發生高檔死亡交叉。
    2. 籌碼面： 判斷籌法是否極度分散
       - 有分點資料：(主力買賣超 <= 主力賣超門檻 AND 外資買賣超 <= 外資賣超門檻) OR (分點買賣家數差 <= 家數差門檻) 
       - 無分點資料 (Fallback)：主力大賣 + 外資大賣 + 投信無護盤(<=0)，達成雙法人同步派發驗證。
    """
    profile = profile or {}

    # 至少需要 5 筆歷史資料
    if len(df_single) < 5:
        if verbose:
            print(f"❌ [你丟我撿] 資料筆數不足 5 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    prev_day = df_single.iloc[-2]  # 用於判斷 KD 死亡交叉

    # --- 1. 從 Profile 讀取門檻設定 ---
    major_sell_limit = profile.get('major_sell', -500)     # 主力賣超門檻 (張)
    foreign_sell_limit = profile.get('foreign_sell', -500) # 外資賣超門檻 (張)
    broker_diff_limit = profile.get('broker_diff', 20)      # 家數差門檻 (正數：買家數 > 賣家數，散戶接盤)

    # --- 2. 提取技術面與籌碼面數據 (安全取得 None / NaN) ---
    easy_a = today.get('easy_buy', None)
    easy_b = today.get('easy_sell', None)
    
    k_val = today.get('K', None)
    d_val = today.get('D', None)
    prev_k = prev_day.get('K', None)
    prev_d = prev_day.get('D', None)

    major_net = today.get('major_net', None)
    foreign_net = today.get('foreign_net', None)
    trust_net = today.get('trust_net', None)
    broker_diff = today.get('broker_diff', None)

    # 輔助函式：檢查是否為有效數值 (非 None 且非 NaN)
    def is_valid(val):
        return val is not None and pd.notna(val)

    # --- 3. 條件邏輯判斷 ---

    # A. 技術面判斷
    cond_easy = (easy_b > easy_a) if (is_valid(easy_a) and is_valid(easy_b)) else True

    cond_kd_overbought = (k_val > 70) if is_valid(k_val) else False
    cond_kd_death_cross = (prev_k > prev_d and k_val < d_val) if all(map(is_valid, [k_val, d_val, prev_k, prev_d])) else False
    cond_tech_kd = cond_kd_overbought or cond_kd_death_cross

    cond_tech = cond_easy and cond_tech_kd

    # B. 籌碼面判斷 (區分「有分點數據」與「無分點備援」)
    cond_chip_main = (major_net <= major_sell_limit) and (foreign_net <= foreign_sell_limit) if (is_valid(major_net) and is_valid(foreign_net)) else False

    # 檢查是否有有效的分點家數差資料
    if is_valid(broker_diff):
        # 情況 1：有分點資料，家數差 >= 門檻 (散戶接盤)
        cond_chip_broker = broker_diff >= broker_diff_limit
        chip_fallback_used = False
    else:
        # 情況 2：缺乏分點資料 (NaN/None)，啟動 Fallback 機制
        # 備援條件：主力大賣 + 外資大賣 + 投信無護盤 (買賣超 <= 0)
        is_trust_not_buying = (trust_net <= 0) if is_valid(trust_net) else True
        cond_chip_broker = cond_chip_main and is_trust_not_buying
        chip_fallback_used = True

    # 籌碼面綜合判定
    cond_chip = cond_chip_main or cond_chip_broker

    # 最終綜合判斷
    is_hit = cond_tech and cond_chip

    # --- 4. 🔔 詳細數據輸出區塊 ---
    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        print("\n" + "=" * 55)
        print(f"🔔 [你丟我撿 訊號檢測分析] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        
        easy_a_str = f"{easy_a:.1f}" if is_valid(easy_a) else "N/A"
        easy_b_str = f"{easy_b:.1f}" if is_valid(easy_b) else "N/A"
        print(f" [{ '✓' if cond_easy else '✕' }] 1. 輕鬆買賣指標 : B(賣) {easy_b_str} > A(買) {easy_a_str}")
        
        k_str = f"{k_val:.1f}" if is_valid(k_val) else "N/A"
        d_str = f"{d_val:.1f}" if is_valid(d_val) else "N/A"
        print(f" [{ '✓' if cond_tech_kd else '✕' }] 2. KD 高檔/死叉 : K值 {k_str} | D值 {d_str}")

        maj_str = f"{major_net:.0f}" if is_valid(major_net) else "N/A"
        for_str = f"{foreign_net:.0f}" if is_valid(foreign_net) else "N/A"
        print(f" [{ '✓' if cond_chip_main else '✕' }] 3. 法人賣超門檻 : 主力 {maj_str} (<= {major_sell_limit}) & 外資 {for_str} (<= {foreign_sell_limit})")

        if not chip_fallback_used:
            bd_str = f"{broker_diff:.0f}" if is_valid(broker_diff) else "N/A"
            print(f" [{ '✓' if cond_chip_broker else '✕' }] 4. 分點籌碼分散 : 買賣家數差 {bd_str} (>= {broker_diff_limit})")
        else:
            tru_str = f"{trust_net:.0f}" if is_valid(trust_net) else "N/A"
            print(f" [{ '✓' if cond_chip_broker else '✕' }] 4. 分點缺失(啟動備援): 外資+主力大賣 且 投信無護盤 ({tru_str} 張)")

        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發你丟我撿]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    # 安全地準備 Info 輸出
    maj_print = f"{major_net:.0f}" if is_valid(major_net) else "0"
    for_print = f"{foreign_net:.0f}" if is_valid(foreign_net) else "0"
    bd_print = f"{broker_diff:.0f}" if is_valid(broker_diff) else "無資料"

    info = {
        '轉空賣訊': '你丟我撿',
        '操作建議': f'股價處於高檔/壓利區且籌碼持續派發（主力 {maj_print} 張 / 外資 {for_print} 張，家數差 {bd_print}），呈現明顯散戶接盤格局，建議逢高減碼。'
    } if is_hit else {}

    return is_hit, info



def mon_qiantang_sell_monitor(df_single: pd.DataFrame, cost_price: float = 0.0, market_above_ma240: bool = True) -> tuple[bool, dict]:
    """
    錢塘潮 11 大轉空/大戶出貨/中途換手監控策略
    
    用於每日針對「已買進持股」進行防禦檢查：
    1. 一柱清香（高檔爆量長上影線/高檔長黑）
    2. 天女散花（高檔籌碼極度分散/大戶大賣散戶大買）
    3. 打鐘下課（跌破關鍵防守線/月線失守）
    4. 中途換手 vs 出貨判定
    """
    
    # 🌟 印出當前股票代號與最新 5 筆資料
    #stock_id = df_single['stock_id'].iloc[-1] if 'stock_id' in df_single.columns else '未知'
    #print(f"\n🔍 [DEBUG] mon_qiantang_sell_monitor 檢視股票: {stock_id} (最新 5 筆)")
    #print(df_single.tail(5).to_string(index=False))
    #print("=" * 60)
    
    if df_single is None or len(df_single) < 60:
        return False, {}

    df = df_single.copy()

    # 指標計算
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA60'] = df['close'].rolling(60).mean()
    df['Vol_MA5'] = df['Trading_Volume'].rolling(5).mean()
    df['Vol_MA20'] = df['Trading_Volume'].rolling(20).mean()

    # K 棒型態指標
    df['K_body'] = abs(df['close'] - df['open'])
    df['Upper_shadow'] = df['max'] - df[['close', 'open']].max(axis=1)
    df['Lower_shadow'] = df[['close', 'open']].min(axis=1) - df['min']

    today = df.iloc[-1]
    prev = df.iloc[-2]

    # 取得指定欄位數值（若不存在則補 0 或 'N/A'）
    sid = today.get('stock_id', 'N/A')
    foreign_net = today.get('foreign_net', 0)
    major_net = today.get('major_net', 0)
    broker_diff = today.get('broker_diff', 0)

    # 🌟 印出指定欄位內容
    print(f"📌 [籌碼檢視] 股票: {sid} | 外資買賣超: {foreign_net} | 主力買賣超: {major_net} | 買賣家數差: {broker_diff}")
    
    close = round(today['close'], 2)
    open_p = today['open']
    high = today['max']
    low = today['min']
    volume = today['Trading_Volume']
    
    # 算當前持股報酬率
    profit_pct = round(((close - cost_price) / cost_price) * 100, 2) if cost_price > 0 else 0.0

    sell_signals = []
    status_type = "正常" # 正常 / 警告 / 建議減碼 / 建議停損落袋

    # ======================================================================
    # 策略 1：【一柱清香】（高檔爆量長上影線 / 避雷針）
    # ======================================================================
    # 條件：成交量暴漲 > 20日均量 2 倍，且上影線長度 > 實體 K 棒 1.5 倍，或高檔開高走極低長黑    
    max_60_today = df['close'].rolling(60).max().iloc[-1] #取出當天滾動 60 日最大值單一數值
    
    is_high_position = close >= (max_60_today * 0.9)
  
    cond_column_incense = (
        is_high_position 
        and (volume >= today['Vol_MA20'] * 2.0) 
        and (today['Upper_shadow'] >= today['K_body'] * 1.5)
    )
    if cond_column_incense:
        sell_signals.append("一柱清香(高檔爆量避雷針)")

    # ======================================================================
    # 策略 2：【天女散花】（主力出貨/籌碼分散）
    # ======================================================================
    # 條件：若有籌碼資料（三大法人賣超 / 買賣家數差為正且大幅擴張）
    foreign_sell = today.get('foreign_investor_net', 0) < 0
    trust_sell = today.get('investment_trust_net', 0) < 0
    broker_diff_positive = today.get('broker_diff', 0) > 0  # 買賣家數差為正表示籌碼分散到散戶

    #print("---------------------------------------\n")
    #print(f"foreign_sell : {today.get('foreign_investor_net', 0)} | trust_sell : {today.get('investment_trust_net', 0)} | broker_diff_positive : {today.get('broker_diff', 0)}")

    
    cond_fairy_flowers = is_high_position and foreign_sell and trust_sell and broker_diff_positive
    if cond_fairy_flowers:
        sell_signals.append("天女散花(法人雙賣/籌碼極度分散)")

    # ======================================================================
    # 策略 3：【打鐘下課】（關鍵趨勢破位）
    # ======================================================================
    # 條件：收盤價跌破 20日月線，且 5日線下彎
    cond_class_dismissed = (close < today['MA20']) and (today['MA5'] < prev['MA5'])
    if cond_class_dismissed:
        sell_signals.append("打鐘下課(跌破20日線趨勢轉弱)")

    # ======================================================================
    # 策略 4：【中途換手 vs 高檔出貨】判讀
    # ======================================================================
    # 爆量黑棒但未跌破 5日/10日線 且 季線強勢向上 -> 視為「中途換手」
    # 爆量黑棒且跌破 5日線 且 季線走平/下彎 -> 視為「大戶出貨」
    cond_big_volume_drop = (close < open_p) and (volume >= today['Vol_MA5'] * 1.5)
    if cond_big_volume_drop:
        if close >= today['MA5'] and today['MA60'] > prev['MA60']:
            sell_signals.append("中途換手(洗盤震盪，可先觀察)")
        else:
            sell_signals.append("大戶出貨(爆量破線，建議逢高減碼)")

    # ======================================================================
    # 訊號彙整與建議 action
    # ======================================================================
    is_hit = len(sell_signals) > 0

    if not is_hit:
        return False, {}

    # 綜合評估建議動作
    signal_str = " | ".join(sell_signals)
    if "打鐘下課" in signal_str or "大戶出貨" in signal_str:
        action_advice = "🚨 建議停損/停利離場"
    elif "一柱清香" in signal_str or "天女散花" in signal_str:
        action_advice = "⚠️ 警訊出現，建議獲利落袋/減碼50%"
    else:
        action_advice = "👀 中途換手觀察，破5日線再離場"

    info = {
        '代號': today.get('stock_id', ''),
        '收盤': close,
        '成本價': cost_price,
        '當前報酬': f"{profit_pct}%",
        '轉空賣訊': signal_str,
        '操作建議': action_advice,
        '成交量倍數': round(volume / today['Vol_MA20'], 2),
        '20日線': round(today['MA20'], 2)
    }

    return True, info



import pandas as pd

def get_qiantang_min_volume_shares(
    price: float, 
    base_lots: int = 3000, 
    profile: dict = None
) -> int:
    """計算錢塘潮策略體系的「最低流動性門檻」(單位：股)
    
    參數:
    - price (float): 當日收盤價 (或評估股價)
    - base_lots (int): 策略原始設定的最低張數門檻 (預設 3000 張，部分策略為 2000 或 4000 張)
    - profile (dict): 個股 Profile 設定檔 (可包含 category 等族群資訊)
    
    傳回:
    - int: 換算後的最低成交量門檻 (單位：股)
    """
    profile = profile or {}
    category = str(profile.get('category', '')).lower()
    
    # 1. 基礎張數門檻 (若 profile 有特別覆寫則優先採用)
    target_lots = profile.get('min_vol_lots', base_lots)
    
    # 2. 針對高價股 / 千金股 / IC設計股進行動態防線下修
    if price >= 1000:
        target_lots = min(target_lots, 300)   # 千金股：防線下修至 300 張
    elif price >= 500:
        target_lots = min(target_lots, 500)   # 500元以上高價股：防線下修至 500 張
    elif 'ic_design' in category or 'ic設計' in category:
        target_lots = min(target_lots, 500)   # IC設計族群預設防線：500 張

    # 3. 轉換為 FinMind API 使用的「股數」單位 (張數 * 1000)
    return int(target_lots * 1000)
