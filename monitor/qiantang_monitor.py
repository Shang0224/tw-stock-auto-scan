import pandas as pd
import numpy as np

from monitor.config import DEBUG_VERBOSE

# ==========================================
# 錢塘潮 11 大防禦賣訊
# ==========================================

DEBUG_VERBOSE = True

def mon_qiantang_didi_chuanxin(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """地底穿心 (極端深跌動態爆量破底 + 融資清籌碼)

    公式 logic:
    1. 收盤 < 輕鬆 B 值 且 收盤 < 輕鬆 S 值 (貫穿雙輕鬆線)
    2. 1天前的輕鬆 B > 1天前的輕鬆 S (加速破底殺盤點)
    3. 當日成交量 ≧ 20日均量 × 2.5倍 且 當日成交金額 ≧ 2億元 (動態相對爆量 + 過濾死水股防線)
    4. 融資張數變動 < 0 或 融資餘額 > 0 (融資洗盤/有槓桿籌碼被逼離場)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    if len(df_single) < 2:
        if verbose:
            print(f"❌ [地底穿心] 資料筆數不足 2 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]      # 當日 (0天前)
    day_1 = df_single.iloc[-2]      # 1天前

    # 1. 價格與技術指標
    close_0 = today.get('close', None)
    easy_b_0 = today.get('easy_b', None)
    easy_s_0 = today.get('easy_s', None)
    easy_b_1 = day_1.get('easy_b', None)
    easy_s_1 = day_1.get('easy_s', None)

    # 2. 量能與成交金額指標
    volume_0 = today.get('volume', None)
    v_ma20_0 = today.get('volume_ma20', None)  # 20日均量
    amount_0 = today.get('amount', None)       # 當日成交金額 (單位: 元)

    # 成交金額備援計算 (若資料集無 amount 欄位，由 收盤價 * 張數 * 1000 股估算)
    if not is_valid(amount_0) and is_valid(close_0) and is_valid(volume_0):
        amount_0 = close_0 * volume_0 * 1000

    # 3. 融資相關指標
    margin_today = today.get('MarginPurchaseTodayBalance', None)
    margin_yday = day_1.get('MarginPurchaseTodayBalance', None)
    margin_diff = (margin_today - margin_yday) if (is_valid(margin_today) and is_valid(margin_yday)) else None

    # --- 條件判定 ---
    # 條件 1: 收盤 < 輕鬆 B 且 收盤 < 輕鬆 S
    cond1_below_bs = (close_0 < easy_b_0 and close_0 < easy_s_0) if (is_valid(close_0) and is_valid(easy_b_0) and is_valid(easy_s_0)) else False

    # 條件 2: 1天前的輕鬆 B > 1天前的輕鬆 S
    cond2_prev_b_gt_s = (easy_b_1 > easy_s_1) if (is_valid(easy_b_1) and is_valid(easy_s_1)) else False

    # 條件 3: 當日成交量 ≧ 20日均量 × 2.5倍 且 當日成交金額 ≧ 2億元
    cond3_vol_surge = (volume_0 >= v_ma20_0 * 2.5) if (is_valid(volume_0) and is_valid(v_ma20_0) and v_ma20_0 > 0) else False
    cond3_amount = (amount_0 >= 200_000_000) if is_valid(amount_0) else False
    cond3_liquidity = cond3_vol_surge and cond3_amount

    # 條件 4: 融資張數變動 < 0 或 融資餘額 > 0
    cond4_margin_clean = False
    margin_msg = "N/A"
    if is_valid(margin_diff) and margin_diff < 0:
        cond4_margin_clean = True
        margin_msg = f"融資大減 {margin_diff:+,.0f} 張 (散戶停損洗盤)"
    elif is_valid(margin_today) and margin_today > 0:
        cond4_margin_clean = True
        margin_msg = f"融資餘額 {margin_today:,.0f} 張 (> 0)"

    # 總體觸發判定
    is_hit = cond1_below_bs and cond2_prev_b_gt_s and cond3_liquidity and cond4_margin_clean

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        
        easy_b_0_str = f"${easy_b_0:.2f}" if is_valid(easy_b_0) else "N/A"
        easy_s_0_str = f"${easy_s_0:.2f}" if is_valid(easy_s_0) else "N/A"
        
        v_ratio_str = f"{volume_0 / v_ma20_0:.2f} 倍" if (is_valid(volume_0) and is_valid(v_ma20_0) and v_ma20_0 > 0) else "N/A"
        amount_ea_str = f"{amount_0 / 100_000_000:.2f} 億" if is_valid(amount_0) else "N/A"

        print("\n" + "=" * 55)
        print(f"🔔 [地底穿心] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_below_bs else '✕' }] 1. 價格貫穿雙輕鬆線 : 收盤 ${close_0 if is_valid(close_0) else 0:.2f} < B值 {easy_b_0_str} 且 < S值 {easy_s_0_str}")
        print(f" [{ '✓' if cond2_prev_b_gt_s else '✕' }] 2. 前一日輕鬆 B > S   : 1天前 B值 ${easy_b_1 if is_valid(easy_b_1) else 0:.2f} > S值 ${easy_s_1 if is_valid(easy_s_1) else 0:.2f}")
        print(f" [{ '✓' if cond3_liquidity else '✕' }] 3. 動態爆量與流動性   : 量放大 {v_ratio_str} (≧ 2.5倍) | 金額 {amount_ea_str} (≧ 2億)")
        print(f" [{ '✓' if cond4_margin_clean else '✕' }] 4. 融資洗盤籌碼防線   : {margin_msg}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發地底穿心]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉多買訊': '地底穿心',
        '操作建議': '股價急跌貫穿雙輕鬆線，並觸發 2.5 倍相對動態爆量（恐慌盤/斷頭潮釋放），同時符合 2 億元流動性低標過濾，適合左側輕倉佈局逆勢抄底反彈。'
    } if is_hit else {}

    return is_hit, info

def mon_qiantang_da_zhong_xia_ke(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """打鐘下課 (純籌碼指標壓軸 - 輕鬆線下彎與法人/籌碼大撤退)

    公式 logic:
    1. 收盤 > 輕鬆線
    2. 輕鬆線 < 1天前的輕鬆線 (輕鬆線下彎)
    3. 買賣家數差 ≦ -30 (若無則以融資餘額增加/散戶進場作為智慧備援替代)
    4. 外資 ≦ -1000 且 投信 ≦ -1000 (法人同步大撤退，中型股固定門檻)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    # 需要至少 2 筆歷史資料以比對輕鬆線變化
    if len(df_single) < 2:
        if verbose:
            print(f"❌ [打鐘下課] 資料筆數不足 2 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]      # 當日 (0天前)
    day_1 = df_single.iloc[-2]      # 1天前

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    easy_1 = day_1.get('easy_line', None)
    
    holder_diff = today.get('holder_diff', None)  # 買賣家數差
    
    # 融資變動計算 (作為無家數差時的智慧備援)
    margin_today = today.get('MarginPurchaseTodayBalance', None)
    margin_yday = day_1.get('MarginPurchaseTodayBalance', None)
    margin_diff = (margin_today - margin_yday) if (is_valid(margin_today) and is_valid(margin_yday)) else 0
    
    foreign_net = today.get('foreign_net', None)  # 外資買賣超
    sitc_net = today.get('sitc_net', None)        # 投信買賣超 (替代主力)

    # 條件 1 & 2: 價格與輕鬆線
    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_easy_down = (easy_0 < easy_1) if (is_valid(easy_0) and is_valid(easy_1)) else False
    
    # 條件 3: 家數差 ≦ -30 (若無則使用融資增加作為智慧備援)
    if is_valid(holder_diff):
        cond3_holder = (holder_diff <= -30)
        holder_mode = f"買賣家數差 {holder_diff} (<= -30)"
    else:
        # 智慧備援：無家數差時，以融資增加（散戶接盤）作為替代判定
        cond3_holder = (margin_diff > 0)
        holder_mode = f"融資變動 {margin_diff:+,.0f} 張 (無家數差之替代備援)"

    # 條件 4: 外資與投信同步撤退 (固定中型股門檻)
    cond4_foreign = (foreign_net <= -1000) if is_valid(foreign_net) else True
    cond4_sitc = (sitc_net <= -1000) if is_valid(sitc_net) else True
    cond4_institutional = cond4_foreign and cond4_sitc

    is_hit = cond1_above_easy and cond2_easy_down and cond3_holder and cond4_institutional

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        
        easy_0_str = f"${easy_0:.2f}" if is_valid(easy_0) else "N/A"
        easy_1_str = f"${easy_1:.2f}" if is_valid(easy_1) else "N/A"
        foreign_str = f"{foreign_net:,}" if is_valid(foreign_net) else "N/A"
        sitc_str = f"{sitc_net:,}" if is_valid(sitc_net) else "N/A"

        print("\n" + "=" * 55)
        print(f"🔔 [打鐘下課] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_above_easy else '✕' }] 1. 收盤 > 輕鬆線     : ${close_0 if is_valid(close_0) else 0:.2f} > {easy_0_str}")
        print(f" [{ '✓' if cond2_easy_down else '✕' }] 2. 輕鬆線下彎       : 當日 {easy_0_str} < 前日 {easy_1_str}")
        print(f" [{ '✓' if cond3_holder else '✕' }] 3. 籌碼發散防線     : {holder_mode}")
        print(f" [{ '✓' if cond4_institutional else '✕' }] 4. 外資與投信雙撤退 : 外資 {foreign_str} | 投信 {sitc_str}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發打鐘下課]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '打鐘下課',
        '操作建議': '股價雖在輕鬆線之上但指標已向下彎曲，搭配籌碼發散（家數差/融資變動）與外資、投信法人同步大舉撤退，中型飆股籌碼全線翻空，強烈建議立即「打鐘下課」離場鎖利。'
    } if is_hit else {}

    return is_hit, info
def mon_qiantang_xia_shan_meng_hu(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """下山猛虎 (1天前強漲後今日直接跌破)

    公式 logic:
    1. 1天前的收盤 / 2天前的收盤 ≧ 1.065
    2. 當日收盤 < 1天前的收盤
    3. 當日成交量 ≧ 20日均量 × 2.5倍 且 當日成交金額 > 2億元 (合併流動性防線)
    4. 當日融券餘額 > 0 或 N/A (智慧容錯)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    # 需要至少 22 筆歷史資料以確保均量與前日數據穩定
    if len(df_single) < 22:
        if verbose:
            print(f"❌ [下山猛虎] 資料筆數不足 22 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]      # 當日 (0天前)
    d1 = df_single.iloc[-2]         # 1天前
    d2 = df_single.iloc[-3]         # 2天前

    close_0 = today.get('close', None)
    close_1 = d1.get('close', None)
    close_2 = d2.get('close', None)
    
    v_0 = today.get('Trading_Volume', None)

    # 1. 數值與比率計算
    surge_ratio_1 = close_1 / close_2 if (is_valid(close_1) and is_valid(close_2) and close_2 > 0) else 0
    
    # 流動性防線數值 (當日 20日均量與成交金額)
    vol_20_ma = today.get('volume_20_ma', 0)
    required_vol_2_5x = vol_20_ma * 2.5
    trading_amount = today.get('trading_amount', close_0 * v_0 if is_valid(close_0) and is_valid(v_0) else 0)
    
    short_balance = today.get('ShortSaleTodayBalance', None)

    # 2. 條件邏輯判斷
    cond1_surge = (surge_ratio_1 >= 1.065)
    cond2_break = (close_0 < close_1) if (is_valid(close_0) and is_valid(close_1)) else False
    
    # 條件 3 & 4 合併為單一防線
    cond3_vol_2_5x = (v_0 >= required_vol_2_5x) if is_valid(v_0) else False
    cond4_amount = (trading_amount > 200_000_000)
    cond3_4_liquidity = cond3_vol_2_5x and cond4_amount

    if is_valid(short_balance) and 'ShortSaleTodayBalance' in df_single.columns:
        cond5_short = (short_balance > 0)
        has_short_col = True
    else:
        cond5_short = True
        has_short_col = False

    is_hit = (
        cond1_surge and cond2_break and cond3_4_liquidity and cond5_short
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        v_0_lots = v_0 / 1000.0 if is_valid(v_0) else 0
        req_lots = required_vol_2_5x / 1000.0

        print("\n" + "=" * 55)
        print(f"🔔 [下山猛虎] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_surge else '✕' }] 1. 1天前強漲 ≧ 6.5%    : 幅度 {surge_ratio_1:.3f} >= 1.065")
        print(f" [{ '✓' if cond2_break else '✕' }] 2. 當日收盤 < 1天前收    : ${close_0 if is_valid(close_0) else 0:.2f} < ${close_1 if is_valid(close_1) else 0:.2f}")
        print(f" [{ '✓' if cond3_4_liquidity else '✕' }] 3. 當日量≧2.5x且額>2億  : 量 {v_0_lots:,.0f}張(門檻 {req_lots:,.0f}) | 金額 ${trading_amount:,.0f}")
        
        if has_short_col:
            print(f" [{ '✓' if cond5_short else '✕' }] 4. 融券餘額 > 0 或 N/A   : 當日融券餘額 {short_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 4. 融券餘額 > 0 或 N/A   : 無欄位資料 (預設通過)")
            
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發下山猛虎]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '下山猛虎',
        '操作建議': f'1天前強勢大漲超過6.5%，今日帶量(成交量達 {v_0 // 1000:,.0f} 張)直接跌破1天前收盤價，顯示短線追高意願潰散、主力出貨翻轉，建議順勢停利或調節。'
    } if is_hit else {}

    return is_hit, info


def mon_qiantang_ming_ri_huang_hua(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """明日黃花 (高檔爆量長紅後反轉跌破)

    公式 logic:
    1. 2天前收盤 / 3天前收盤 ≧ 1.065
    2. 1天前收盤 ≧ 2天前收盤
    3. 當日收盤 < 2天前收盤
    4. 2天前成交量 == 2天前的 21 天成交量最大值
    5. 2天前成交量 ≧ 20日均量 × 2.5倍 且 2天前成交金額 > 2億元 (歷史防線)
    6. 當日融券餘額 > 0 或 N/A (智慧容錯)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    # 需要至少 23 筆資料以確保能往前計算 21 天最大量與均量
    if len(df_single) < 23:
        if verbose:
            print(f"❌ [明日黃花] 資料筆數不足 23 筆 (目前: {len(df_single)})")
        return False, {}

    # 取得相關日期的資料列
    today = df_single.iloc[-1]       # 當日 (0天前)
    d1 = df_single.iloc[-2]          # 1天前
    d2 = df_single.iloc[-3]          # 2天前
    d3 = df_single.iloc[-4]          # 3天前

    close_0 = today['close']
    close_1 = d1['close']
    close_2 = d2['close']
    close_3 = d3['close']
    
    v_2 = d2.get('Trading_Volume', 0)

    # 1. 數值與區間極值計算 (針對 2 天前作檢核)
    surge_ratio_2 = close_2 / close_3 if (is_valid(close_3) and close_3 > 0) else 0
    
    # 計算 2 天前的 21 天成交量最大值 (視窗從 -23 到 -3)
    max_21_vol_at_d2 = df_single['Trading_Volume'].iloc[-23:-3].max()
    
    d2_volume_20_ma = d2.get('volume_20_ma', 0)
    d2_required_vol_2_5x = d2_volume_20_ma * 2.5
    d2_trading_amount = d2.get('trading_amount', close_2 * v_2)
    
    short_balance = today.get('ShortSaleTodayBalance', None)

    # 條件邏輯判斷
    cond1_surge = (surge_ratio_2 >= 1.065)
    cond2_hold = (close_1 >= close_2)
    cond3_break = (close_0 < close_2)
    cond4_vol_peak = (v_2 == max_21_vol_at_d2)
    
    cond5_vol_2_5x = (v_2 >= d2_required_vol_2_5x)
    cond6_amount = (d2_trading_amount > 200_000_000)
    cond5_6_liquidity = cond5_vol_2_5x and cond6_amount

    if is_valid(short_balance) and 'ShortSaleTodayBalance' in df_single.columns:
        cond7_short = (short_balance > 0)
        has_short_col = True
    else:
        cond7_short = True
        has_short_col = False

    is_hit = (
        cond1_surge and cond2_hold and cond3_break and 
        cond4_vol_peak and cond5_6_liquidity and cond7_short
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        v_2_lots = v_2 / 1000.0
        req_lots = d2_required_vol_2_5x / 1000.0

        print("\n" + "=" * 55)
        print(f"🔔 [明日黃花] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_surge else '✕' }] 1. 2天前強漲 ≧ 6.5%    : 幅度 {surge_ratio_2:.3f} >= 1.065")
        print(f" [{ '✓' if cond2_hold else '✕' }] 2. 1天前收盤 ≧ 2天前收   : ${close_1:.2f} >= ${close_2:.2f}")
        print(f" [{ '✓' if cond3_break else '✕' }] 3. 當日收盤 < 2天前收    : ${close_0:.2f} < ${close_2:.2f}")
        print(f" [{ '✓' if cond4_vol_peak else '✕' }] 4. 2天前量==21日量極值   : 2天前量 {v_2/1000:,.0f} == 21日大 {max_21_vol_at_d2/1000:,.0f}")
        print(f" [{ '✓' if cond5_6_liquidity else '✕' }] 5. 2天前量≧2.5x且額>2億  : 量 {v_2_lots:,.0f}張(門檻 {req_lots:,.0f}) | 金額 ${d2_trading_amount:,.0f}")
        
        if has_short_col:
            print(f" [{ '✓' if cond7_short else '✕' }] 6. 融券餘額 > 0 或 N/A   : 當日融券餘額 {short_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 6. 融券餘額 > 0 或 N/A   : 無欄位資料 (預設通過)")
            
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發明日黃花]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '明日黃花',
        '操作建議': f'2天前爆量長紅大漲後，經過1天高檔整理，今日直接跌破2天前收盤價，顯示攻擊力道受挫、主力有誘多嫌疑，建議順勢調節。'
    } if is_hit else {}

    return is_hit, info

def mon_qiantang_ming_ri_huang_hua_old(
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

def mon_qiantang_tian_nv_san_hua(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """天女散花 (高檔急拉爆量留上影線)

    公式 logic:
    1. 當日最高 == 近 10 天最高價
    2. 當日成交量 == 近 10 天成交量最大值
    3. 當日融券餘額 > 0 或 N/A (智慧容錯)
    4. (當日最高 / 1天前收盤) > 1.065
    5. (當日最高 / 當日收盤) ≧ 1.01
    6. 當日成交量 ≧ 20日均量 × 2.5倍 且 當日成交金額 > 2億元 (升級流動性防線)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    if len(df_single) < 20:
        if verbose:
            print(f"❌ [天女散花] 資料筆數不足 20 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    prev_day = df_single.iloc[-2]
    
    close = today['close']
    prev_close = prev_day['close']
    high = today.get('max', 0)
    v_0 = today.get('Trading_Volume', 0)

    # 1. 條件數值計算
    max_10_high = df_single['max'].iloc[-10:].max()
    max_10_vol = df_single['Trading_Volume'].iloc[-10:].max()
    
    ratio_prev = high / prev_close if (is_valid(prev_close) and prev_close > 0) else 0
    ratio_close = high / close if (is_valid(close) and close > 0) else 0
    
    volume_20_ma = today.get('volume_20_ma', 0)
    required_vol_2_5x = volume_20_ma * 2.5
    trading_amount = today.get('trading_amount', close * v_0)
    
    short_balance = today.get('ShortSaleTodayBalance', None)

    # 條件邏輯判斷
    cond1_max_price = (high == max_10_high)
    cond2_max_vol = (v_0 == max_10_vol)
    
    if is_valid(short_balance) and 'ShortSaleTodayBalance' in df_single.columns:
        cond3_short = (short_balance > 0)
        has_short_col = True
    else:
        cond3_short = True
        has_short_col = False

    cond4_ratio_prev = (ratio_prev > 1.065)
    cond5_ratio_close = (ratio_close >= 1.01)
    
    cond6_vol_2_5x = (v_0 >= required_vol_2_5x)
    cond7_amount = (trading_amount > 200_000_000)
    cond6_7_liquidity = cond6_vol_2_5x and cond7_amount

    is_hit = (
        cond1_max_price and cond2_max_vol and cond3_short and 
        cond4_ratio_prev and cond5_ratio_close and cond6_7_liquidity
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        v_0_lots = v_0 / 1000.0
        req_lots = required_vol_2_5x / 1000.0

        print("\n" + "=" * 55)
        print(f"🔔 [天女散花] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_max_price else '✕' }] 1. 最高等於10日最高     : 最高價 {high:.2f} == 10日最高 {max_10_high:.2f}")
        print(f" [{ '✓' if cond2_max_vol else '✕' }] 2. 成交量等於10日最大量   : 當日量 {v_0/1000:,.0f} == 10日最大量 {max_10_vol/1000:,.0f}")
        
        if has_short_col:
            print(f" [{ '✓' if cond3_short else '✕' }] 3. 融券餘額 > 0 或 N/A  : 當日融券餘額 {short_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 3. 融券餘額 > 0 或 N/A  : 無欄位資料 (預設通過)")
            
        print(f" [{ '✓' if cond4_ratio_prev else '✕' }] 4. 最高/昨收 > 1.065    : 比例 {ratio_prev:.3f} > 1.065")
        print(f" [{ '✓' if cond5_ratio_close else '✕' }] 5. 最高/收盤 ≧ 1.01     : 比例 {ratio_close:.3f} >= 1.01")
        print(f" [{ '✓' if cond6_7_liquidity else '✕' }] 6. 量≧2.5x且金額>2億      : 量 {v_0_lots:,.0f}張(門檻 {req_lots:,.0f}) | 金額 ${trading_amount:,.0f}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發天女散花]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '天女散花',
        '操作建議': f'高檔急拉超過6.5%且成交量創10天新高，盤中大漲後遇壓回落留下上影線（最高/收盤比率 {ratio_close:.2f}），多方力道消耗殆盡，建議逢高獲利了結。'
    } if is_hit else {}

    return is_hit, info



def mon_qiantang_he_shi(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """合十 (高檔十字變盤線)

    公式 logic:
    1. 收盤 == 開盤 (十字線，允許微小 tick 誤差)
    2. 最高 != 最低 (排除極端無波動值)
    3. 當日最高 == 近 10 天最高價 (含當日)
    4. 收盤 != 最高 (帶有上影線)
    5. 近 2 天成交量最大值 == 近 21 天成交量最大值
    6. 當日融券餘額 > 0 或 N/A (智慧容錯)
    7. 當日成交量 ≧ 20日均量 × 2.5倍 且 當日成交金額 > 2億元 (升級流動性防線)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    if len(df_single) < 21:
        if verbose:
            print(f"❌ [合十] 資料筆數不足 21 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    close = today['close']
    open_p = today['open']
    high = today.get('max', 0)
    low = today.get('min', 0)
    v_0 = today.get('Trading_Volume', 0)

    # 1. 條件數值計算
    max_10_high = df_single['max'].iloc[-10:].max()
    
    max_2d_vol = df_single['Trading_Volume'].iloc[-2:].max()
    max_21_vol = df_single['Trading_Volume'].iloc[-21:].max()
    
    volume_20_ma = today.get('volume_20_ma', 0)
    required_vol_2_5x = volume_20_ma * 2.5
    trading_amount = today.get('trading_amount', close * v_0)
    
    short_balance = today.get('ShortSaleTodayBalance', None)

    # 條件邏輯判斷
    cond1_doji = (close == open_p) or (abs(close - open_p) <= 0.01)
    cond2_range = (high != low)
    cond3_max_price = (high == max_10_high)
    cond4_close_not_high = (close != high)
    cond5_vol_peak = (max_2d_vol == max_21_vol)
    
    if is_valid(short_balance) and 'ShortSaleTodayBalance' in df_single.columns:
        cond6_short = (short_balance > 0)
        has_short_col = True
    else:
        cond6_short = True
        has_short_col = False

    cond7_vol_2_5x = (v_0 >= required_vol_2_5x)
    cond8_amount = (trading_amount > 200_000_000)
    
    # 合併 7 與 8 的綜合流動性防線判定
    cond7_8_liquidity = cond7_vol_2_5x and cond8_amount

    is_hit = (
        cond1_doji and cond2_range and cond3_max_price and 
        cond4_close_not_high and cond5_vol_peak and 
        cond6_short and cond7_8_liquidity
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        v_0_lots = v_0 / 1000.0
        req_lots = required_vol_2_5x / 1000.0

        print("\n" + "=" * 55)
        print(f"🔔 [合十] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_doji else '✕' }] 1. 收盤 == 開盤 (十字線)  : 收 ${close:.2f} == 開 ${open_p:.2f}")
        print(f" [{ '✓' if cond2_range else '✕' }] 2. 最高 != 最低         : 最高 ${high:.2f} != 最低 ${low:.2f}")
        print(f" [{ '✓' if cond3_max_price else '✕' }] 3. 最高等於10日最高     : 最高價 {high:.2f} == 10日最高 {max_10_high:.2f}")
        print(f" [{ '✓' if cond4_close_not_high else '✕' }] 4. 收盤 != 最高         : 收盤 ${close:.2f} != 最高 ${high:.2f}")
        print(f" [{ '✓' if cond5_vol_peak else '✕' }] 5. 近2日量極==21日極值: 近2日大 {max_2d_vol/1000:,.0f} == 21日大 {max_21_vol/1000:,.0f}")
        
        if has_short_col:
            print(f" [{ '✓' if cond6_short else '✕' }] 6. 融券餘額 > 0 或 N/A  : 當日融券餘額 {short_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 6. 融券餘額 > 0 或 N/A  : 無欄位資料 (預設通過)")
            
        print(f" [{ '✓' if cond7_8_liquidity else '✕' }] 7. 量≧2.5x且金額>2億      : 量 {v_0_lots:,.0f}張(門檻 {req_lots:,.0f}) | 金額 ${trading_amount:,.0f}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發合十]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '合十',
        '操作建議': f'高檔出現十字變盤線（合十），最高創10天新高且近2日量能創21天新高，流動性與融券條件皆符合，多空力道均衡面臨轉折，建議提高警覺。'
    } if is_hit else {}

    return is_hit, info


def mon_qiantang_yi_zhu_qing_xiang(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """一柱清香 (原始邏輯 + 升級量能防線)

    公式 logic:
    1. (最高 / 收盤) ≧ 1.03
    2. 融券餘額 > 0 或 N/A (智慧容錯)
    3. 近 2 天最高價最大值 == 近 9 天最高價最大值
    4. 近 2 天成交量最大值 == 近 9 天成交量最大值
    5. 當日成交量 ≧ 20日均量 × 2.5倍 且 當日成交金額 > 2億元 (升級流動性防線)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    if len(df_single) < 20:
        if verbose:
            print(f"❌ [一柱清香] 資料筆數不足 20 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    close = today['close']
    high = today.get('max', 0)
    v_0 = today.get('Trading_Volume', 0)

    # 1. 條件數值計算
    high_close_ratio = high / close if (is_valid(close) and close > 0) else 0
    
    max_2d_high = df_single['max'].iloc[-2:].max()
    max_9d_high = df_single['max'].iloc[-9:].max()
    
    max_2d_vol = df_single['Trading_Volume'].iloc[-2:].max()
    max_9d_vol = df_single['Trading_Volume'].iloc[-9:].max()
    
    volume_20_ma = today.get('volume_20_ma', 0)
    required_vol_2_5x = volume_20_ma * 2.5
    trading_amount = today.get('trading_amount', close * v_0)
    
    short_balance = today.get('ShortSaleTodayBalance', None)

    # 條件邏輯判斷
    cond1_ratio = (high_close_ratio >= 1.03)
    
    if is_valid(short_balance) and 'ShortSaleTodayBalance' in df_single.columns:
        cond2_short = (short_balance > 0)
        has_short_col = True
    else:
        cond2_short = True
        has_short_col = False

    cond3_max_price = (max_2d_high == max_9d_high)
    cond4_max_vol = (max_2d_vol == max_9d_vol)
    cond5_vol_2_5x = (v_0 >= required_vol_2_5x)
    cond6_amount = (trading_amount > 200_000_000)
    
    # 合併 5 與 6 的綜合流動性防線判定
    cond5_6_liquidity = cond5_vol_2_5x and cond6_amount

    is_hit = (
        cond1_ratio and cond2_short and 
        cond3_max_price and cond4_max_vol and 
        cond5_6_liquidity
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        v_0_lots = v_0 / 1000.0
        req_lots = required_vol_2_5x / 1000.0

        print("\n" + "=" * 55)
        print(f"🔔 [一柱清香] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_ratio else '✕' }] 1. 最高/收盤 ≧ 1.03       : 比例 {high_close_ratio:.3f} >= 1.03")
        
        if has_short_col:
            print(f" [{ '✓' if cond2_short else '✕' }] 2. 融券餘額 > 0 或 N/A    : 當日融券餘額 {short_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 2. 融券餘額 > 0 或 N/A    : 無欄位資料 (預設通過)")
            
        print(f" [{ '✓' if cond3_max_price else '✕' }] 3. 近2日高極==9日高極值   : 近2日高 {max_2d_high:.2f} == 9日高 {max_9d_high:.2f}")
        print(f" [{ '✓' if cond4_max_vol else '✕' }] 4. 近2日量極==9日量極值   : 近2日量 {max_2d_vol/1000:,.0f} == 9日量 {max_9d_vol/1000:,.0f}")
        print(f" [{ '✓' if cond5_6_liquidity else '✕' }] 5. 量≧2.5x且金額>2億      : 量 {v_0_lots:,.0f}張(門檻 {req_lots:,.0f}) | 金額 ${trading_amount:,.0f}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發一柱清香]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '一柱清香',
        '操作建議': f'高檔留有長上影線（最高/收盤比率 {high_close_ratio:.2f}），近2日量價創9天新高且量能與金額達標，主力有出貨嫌疑，建議逢高調節。'
    } if is_hit else {}

    return is_hit, info

def mon_qiantang_jiang_long_fu_hu(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """降龍伏虎 (高檔紡錘線變盤)

    公式 logic:
    1. 形態：陽紡錘 或 陰紡錘 (實體小、上下影線明顯)
    2. 當日最高 == 近 21 天最高價 (含當日)
    3. 當日成交量 ≧ 20日均量 × 2.5倍
    4. 當日成交金額 > 2億元
    5. 近 2 天成交量最大值 == 近 21 天成交量最大值
    6. 當日融資餘額 > 0 或 N/A (智慧容錯)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    if len(df_single) < 21:
        if verbose:
            print(f"❌ [降龍伏虎] 資料筆數不足 21 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    close = today['close']
    open_p = today['open']
    high = today.get('max', 0)
    low = today.get('min', 0)
    v_0 = today.get('Trading_Volume', 0)

    # 1. 紡錘線 (Spinning Top) 形態計算
    total_range = high - low
    if total_range == 0:
        is_spinning_top = False
        is_yang_spinning = False
        is_yin_spinning = False
    else:
        body = abs(close - open_p)
        upper_shadow = high - max(open_p, close)
        lower_shadow = min(open_p, close) - low
        
        # 紡錘線標準：實體較小 (小於總振幅的 35%)，且上下影線皆大於實體
        is_spinning_top = (body <= total_range * 0.35) and (upper_shadow > body) and (lower_shadow > body)
        is_yang_spinning = (close > open_p) and is_spinning_top
        is_yin_spinning = (close < open_p) and is_spinning_top

    # 提取各項指標數值
    max_21_high = df_single['max'].iloc[-21:].max()
    volume_20_ma = today.get('volume_20_ma', 0)
    required_vol_2_5x = volume_20_ma * 2.5
    trading_amount = today.get('trading_amount', close * v_0)
    
    max_2d_vol = df_single['Trading_Volume'].iloc[-2:].max()
    max_21_vol = df_single['Trading_Volume'].iloc[-21:].max()
    
    margin_balance = today.get('MarginPurchaseTodayBalance', None)

    # 條件邏輯判斷
    cond1_spinning = is_spinning_top
    cond2_max_price = (high == max_21_high)
    cond3_vol_2_5x = (v_0 >= required_vol_2_5x)
    cond4_amount = (trading_amount > 200_000_000)
    cond5_vol_peak = (max_2d_vol == max_21_vol)

    if is_valid(margin_balance) and 'MarginPurchaseTodayBalance' in df_single.columns:
        cond6_margin = (margin_balance > 0)
        has_margin_col = True
    else:
        cond6_margin = True
        has_margin_col = False

    is_hit = (
        cond1_spinning and cond2_max_price and cond3_vol_2_5x and 
        cond4_amount and cond5_vol_peak and cond6_margin
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        shape_name = "陽紡錘" if is_yang_spinning else ("陰紡錘" if is_yin_spinning else "非標準紡錘")

        print("\n" + "=" * 55)
        print(f"🔔 [降龍伏虎] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_spinning else '✕' }] 1. 紡錘線形態 ({shape_name}) : 實體小與上下影線符合")
        print(f" [{ '✓' if cond2_max_price else '✕' }] 2. 最高等於21日最高   : 最高價 {high:.2f} == 21日最高 {max_21_high:.2f}")
        print(f" [{ '✓' if cond3_vol_2_5x else '✕' }] 3. 量 ≧ 20日均量×2.5    : 當日量 {v_0/1000:,.0f} 張 >= 門檻 {required_vol_2_5x/1000:,.0f} 張")
        print(f" [{ '✓' if cond4_amount else '✕' }] 4. 成交金額 > 2億元     : 金額 ${trading_amount:,.0f} 元 > 2億")
        print(f" [{ '✓' if cond5_vol_peak else '✕' }] 5. 近2日量極==21日極值: 近2日大 {max_2d_vol/1000:,.0f} == 21日大 {max_21_vol/1000:,.0f}")
        
        if has_margin_col:
            print(f" [{ '✓' if cond6_margin else '✕' }] 6. 融資餘額 > 0 或 N/A  : 當日融資餘額 {margin_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 6. 融資餘額 > 0 或 N/A  : 無欄位資料 (預設通過)")
            
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發降龍伏虎]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '降龍伏虎',
        '操作建議': f'高檔出現紡錘線變盤訊號，且成交量創21天新高達20日均量2.5倍以上，成交金額突破2億元，多空交戰激烈、主力有散心出貨疑慮，建議提高警覺。'
    } if is_hit else {}

    return is_hit, info


def mon_qiantang_dang_tou_bang_he(
    df_single: pd.DataFrame, 
    profile: dict = None, 
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """當頭棒喝 (創高長黑K)

    公式 logic:
    1. 收盤 < 開盤 (黑K)
    2. 當日成交量 == 近 34 天成交量最大值 (含當日)
    3. 當日成交量 ≧ 20日均量 × 2.5倍
    4. 當日成交金額 > 2億元
    5. 當日融資餘額 > 0 或 N/A (智慧容錯)
    6. 當日最高價 == 近 10 天最高價 (含當日)
    """
    profile = profile or {}

    def is_valid(val):
        return val is not None and pd.notna(val)

    if len(df_single) < 34:
        if verbose:
            print(f"❌ [當頭棒喝] 資料筆數不足 34 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    close = today['close']
    open_p = today['open']
    v_0 = today.get('Trading_Volume', 0)
    high = today.get('max', 0)

    # 提取指標數值
    max_34_vol = df_single['Trading_Volume'].iloc[-34:].max()
    volume_20_ma = today.get('volume_20_ma', 0)
    required_vol_2_5x = volume_20_ma * 2.5
    trading_amount = today.get('trading_amount', close * v_0)
    margin_balance = today.get('MarginPurchaseTodayBalance', None)
    max_10_high = df_single['max'].iloc[-10:].max()

    # 條件邏輯判斷
    cond1_black_k = (close < open_p)
    cond2_34d_max_vol = (v_0 == max_34_vol)
    cond3_vol_2_5x = (v_0 >= required_vol_2_5x)
    cond4_amount = (trading_amount > 200_000_000)

    if is_valid(margin_balance) and 'MarginPurchaseTodayBalance' in df_single.columns:
        cond5_margin = (margin_balance > 0)
        has_margin_col = True
    else:
        cond5_margin = True
        has_margin_col = False

    cond6_10d_max_high = (high == max_10_high)

    is_hit = (
        cond1_black_k and cond2_34d_max_vol and cond3_vol_2_5x and 
        cond4_amount and cond5_margin and cond6_10d_max_high
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))

        print("\n" + "=" * 55)
        print(f"🔔 [當頭棒喝] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f" [{ '✓' if cond1_black_k else '✕' }] 1. 收盤 < 開盤 (黑K)       : 收 ${close:.2f} < 開 ${open_p:.2f}")
        print(f" [{ '✓' if cond2_34d_max_vol else '✕' }] 2. 量 = 34日最大量        : 當日量 {v_0/1000:,.0f} 張 == 34日大 {max_34_vol/1000:,.0f} 張")
        print(f" [{ '✓' if cond3_vol_2_5x else '✕' }] 3. 量 ≧ 20日均量×2.5      : 當日量 {v_0/1000:,.0f} 張 >= 門檻 {required_vol_2_5x/1000:,.0f} 張")
        print(f" [{ '✓' if cond4_amount else '✕' }] 4. 成交金額 > 2億元        : 金額 ${trading_amount:,.0f} 元 > 2億")
        
        if has_margin_col:
            print(f" [{ '✓' if cond5_margin else '✕' }] 5. 融資餘額 > 0 或 N/A     : 當日融資餘額 {margin_balance:,.0f} 張 > 0")
        else:
            print(f" [–] 5. 融資餘額 > 0 或 N/A     : 無欄位資料 (預設通過)")
            
        print(f" [{ '✓' if cond6_10d_max_high else '✕' }] 6. 最高 = 10日最大高      : 最高價 {high:.2f} == 10日最高 {max_10_high:.2f}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發當頭棒喝]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '轉空賣訊': '當頭棒喝',
        '操作建議': f'高檔巨量長黑K，成交量創34天新高({v_0 // 1000:,.0f} 張)且達20日均量2.5倍以上，成交金額突破2億元，多頭力竭，極易形成中期頭部，建議避險。'
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
