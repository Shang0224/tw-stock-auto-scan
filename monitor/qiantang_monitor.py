import pandas as pd
import numpy as np

import pandas as pd
import numpy as np


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


def mon_qiantang_ming_ri_huang_hua(df_single: pd.DataFrame, profile: dict):
    """明日黃花 (創高爆量滯漲)"""
    #2天前的收盤 / 3天前的收盤 ≧ 1.065 且 1天前的收盤 ≧ 2天前的收盤 
    #且 收盤 < 2天前的收盤 且 2天前的成交量  ≧ 3000 且 2天前的成交量 = 2天前的21天成交量最大值 且 融券餘額 > 0
    if len(df_single) < 20: return False, {}
    today = df_single.iloc[-1]
    
    surge_mult = profile.get('surge_mult', 1.0)
    vol_burst = today.get('Trading_Volume', 0) > (df_single['Trading_Volume'].iloc[-20:-1].max() * 0.9)
    pct_change = abs(today['close'] - today['open']) / today['open']
    is_stagnant = pct_change < (0.01 * surge_mult)
    
    is_hit = vol_burst and is_stagnant
    info = {
        '轉空賣訊': '明日黃花',
        '操作建議': '成交量創巨量但股價滯漲，籌碼高檔密集換手派發，隨時有轉空風險。'
    } if is_hit else {}
    
    return is_hit, info


def mon_qiantang_tian_nv_san_hua(df_single: pd.DataFrame, profile: dict):
    """天女散花 (高檔長下影/籌碼鬆動)"""
    if len(df_single) < 20: return False, {}
    today = df_single.iloc[-1]
    
    total_range = today['max'] - today['min']
    if total_range == 0: return False, {}
    
    lower_shadow = min(today['open'], today['close']) - today['min']
    is_long_lower = (lower_shadow / total_range) >= 0.60
    is_high_area = today['close'] >= df_single['close'].iloc[-20:].max() * 0.95
    
    is_hit = is_long_lower and is_high_area
    info = {
        '轉空賣訊': '天女散花',
        '操作建議': '高檔出現巨量長下影線，代表主力籌碼大幅鬆動控盤不穩，宜逢高分批停利。'
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


def mon_qiantang_da_zhong_xia_ke(df_single: pd.DataFrame, profile: dict):
    """打鐘下課 (主力法人大賣)"""
    if len(df_single) < 5: return False, {}
    today = df_single.iloc[-1]
    
    major_net = today.get('major_net', 0)
    foreign_net = today.get('foreign_net', 0)
    major_sell_limit = profile.get('major_sell', -800)
    
    is_hit = (major_net < major_sell_limit) or (foreign_net < major_sell_limit)
    info = {
        '轉空賣訊': '打鐘下課',
        '操作建議': '法人與主力單日出現巨量拋售，籌碼面顯著惡化，宜儘速退場。'
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
