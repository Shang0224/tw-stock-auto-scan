import pandas as pd
import numpy as np

from monitor.config import DEBUG_VERBOSE

# ==========================================
# 錢塘潮 11 大防禦賣訊
# ==========================================

def mon_qiantang_yi_zhu_qing_xiang(df_single: pd.DataFrame, profile: dict):
    """一柱清香 (高檔爆量長上影)"""
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

def mon_qiantang_ming_ri_huang_hua(df_single: pd.DataFrame, profile: dict = None):
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

def mon_qiantang_tian_nv_san_hua(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEFAULT_VERBOSE
) -> tuple[bool, dict]:
    """天女散花 (高檔長下影 / 創高爆量籌碼鬆動)
    
    核心邏輯：
    1. 當日最高價 >= 近 10 天最高價 (創階段新高) 且
    2. 當日成交量 >= 近 10 天最大成交量 (頂部天量換手) 且
    3. 當日成交量 >= 最低流動性門檻 (高價 IC 設計股自動向下微調) 且
    4. 當日最高價 / 1天前收盤 > (1 + 0.065 * surge_mult) (衝高強勢拉抬) 且
    5. 當日最高價 / 當日收盤 >= 1.01 (頂部滯漲或震盪留上影線) 且
    6. 長下影線特徵：(min(open, close) - min) / (max - min) >= 0.60 且
    7. 融券餘額 > 0 (若資料庫包含該欄位)
    """
    profile = profile or {}

    # 至少需要 15 筆歷史資料支援 10 天視窗運算
    if len(df_single) < 15:
        if verbose:
            print(f"❌ [天女散花] 資料筆數不足 15 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    c_1 = df_single['close'].iloc[-2]  # 前一日收盤價

    total_range = today['max'] - today['min']
    if total_range == 0:
        if verbose:
            print("❌ [天女散花] 當日高低價差為 0 (平盤無震盪)")
        return False, {}

    # 1. 讀取 Profile 基礎設定與參數
    base_min_vol = profile.get('min_vol', 1000)
    surge_mult = profile.get('surge_mult', 1.0)
    profile_category = profile.get('category', '')

    # 2. 流動性門檻調整 (高價 IC 設計股自動微調)
    min_vol = base_min_vol
    if profile_category == 'ic_design':
        if today['close'] >= 1000:
            min_vol = min(base_min_vol, 300)
        elif today['close'] >= 500:
            min_vol = min(base_min_vol, 500)

    # 3. 計算動態衝高門檻 (基準 6.5% 乘以族群波動係數)
    target_surge_ratio = 1.0 + (0.065 * surge_mult)

    # 4. 提取各指標數值
    max_10d = df_single['max'].iloc[-10:].max()
    vol_10d = df_single['Trading_Volume'].iloc[-10:].max()
    surge_ratio = today['max'] / c_1
    high_close_ratio = today['max'] / today['close']
    lower_shadow = min(today['open'], today['close']) - today['min']
    lower_shadow_ratio = lower_shadow / total_range
    short_balance = today.get('Margin_Short_Balance', None)

    # 5. 條件邏輯判斷
    cond1_max_price = today['max'] >= max_10d
    cond2_max_vol = today['Trading_Volume'] >= vol_10d
    cond3_min_vol = today['Trading_Volume'] >= min_vol
    cond4_surge = surge_ratio > target_surge_ratio
    cond5_high_close_ratio = high_close_ratio >= 1.01
    cond6_long_lower = lower_shadow_ratio >= 0.60
    cond7_short_balance = (
        (short_balance > 0) 
        if (short_balance is not None and 'Margin_Short_Balance' in df_single.columns) 
        else True
    )

    # 6. 綜合評估
    is_hit = (
        cond1_max_price and 
        cond2_max_vol and 
        cond3_min_vol and 
        cond4_surge and 
        cond5_high_close_ratio and 
        cond6_long_lower and 
        cond7_short_balance
    )

    # 7. 🔔 詳細數據輸出區塊 (受到 verbose 開關控制)
    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        print("\n" + "=" * 55)
        print(f"🔔 [天女散花 訊號檢測分析] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_max_price else '✕' }] 1. 創 10 日新高 : 最高價 {today['max']:.2f} >= 近10日最高 {max_10d:.2f}")
        print(f" [{ '✓' if cond2_max_vol else '✕' }] 2. 創 10 日天量 : 當日量 {today['Trading_Volume']:.0f} >= 近10日最大量 {vol_10d:.0f}")
        print(f" [{ '✓' if cond3_min_vol else '✕' }] 3. 達最低流動性 : 當日量 {today['Trading_Volume']:.0f} >= 門檻 {min_vol} 張")
        print(f" [{ '✓' if cond4_surge else '✕' }] 4. 強勢衝高幅度 : 高點/前收 {surge_ratio:.3f} > 門檻 {target_surge_ratio:.3f} (+{(target_surge_ratio-1)*100:.1f}%)")
        print(f" [{ '✓' if cond5_high_close_ratio else '✕' }] 5. 頂部滯漲震盪 : 高點/收盤 {high_close_ratio:.3f} >= 1.010")
        print(f" [{ '✓' if cond6_long_lower else '✕' }] 6. 長下影線比例 : 下影線佔比 {lower_shadow_ratio*100:.1f}% >= 60.0%")
        
        if short_balance is not None and 'Margin_Short_Balance' in df_single.columns:
            print(f" [{ '✓' if cond7_short_balance else '✕' }] 7. 融券餘額檢查 : 當日融券餘額 {short_balance:.0f} > 0")
        else:
            print(f" [–] 7. 融券餘額檢查 : 無欄位資料 (預設通過)")
            
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發天女散花]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '天女散花',
        '操作建議': f'高檔爆出近10天天量(當日套用門檻 {min_vol} 張)且出現劇烈震盪長下影線，代表主力籌碼大幅鬆動控盤不穩，宜逢高分批停利離場。'
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


import pandas as pd

def mon_qiantang_da_zhong_xia_ke(df_single: pd.DataFrame, profile: dict = None):
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


def mon_qiantang_ni_diu_wo_jian(df_single: pd.DataFrame, profile: dict):
    """你丟我撿 (主力持續派發/散戶接盤)"""
    if len(df_single) < 5: return False, {}
    
    if 'major_net' in df_single.columns:
        recent_3_major = df_single['major_net'].iloc[-3:]
        is_hit = (recent_3_major < 0).all()
    else:
        is_hit = False
        
    info = {
        '轉空賣訊': '你丟我撿',
        '操作建議': '主力籌碼連續多日流出，呈現出貨格局，反彈宜賣不宜買。'
    } if is_hit else {}
    
    return is_hit, info


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
    """輕鬆線轉空 (輕鬆線死亡交叉)"""
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
    """KD高檔死叉 (過熱區死亡交叉)"""
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
