# strategy/qiantang_strategies.py
"""
錢塘潮選股系統 - 7 大多方選股策略模組 (qiantang_strategies.py)
說明：完全對齊 monitor/qiantang_monitor.py 之除錯訊息 (verbose) 輸出機制與回傳格式 (is_hit, info)。
"""

import pandas as pd
import numpy as np
from monitor.config import DEBUG_VERBOSE


def is_valid(val):
    """檢查值是否非空且非 NaN"""
    return val is not None and pd.notna(val)


# =====================================================================
# F1. 筆張現形
# =====================================================================
def st_qiantang_f1_spt_growth(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F1_筆張現形】
    邏輯：
    1. 收盤價 > 輕鬆線 (easy_line)
    2. 單筆均張 (shares_per_trans) 連續 2 日遞增 (t > t-1 > t-2)
    3. 當日成交量 >= 500 張 (500,000 股)
    """
    profile = profile or {}
    if len(df_single) < 3:
        if verbose:
            print(f"❌ [筆張現形] 資料筆數不足 3 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)

    spt_0 = today.get('shares_per_trans', None)
    spt_1 = d1.get('shares_per_trans', None)
    spt_2 = d2.get('shares_per_trans', None)

    # 1. 上輕鬆
    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    
    # 2. 單筆均張遞增 (t > t-1 > t-2)
    cond2_spt_growing = (spt_0 > spt_1 > spt_2) if (is_valid(spt_0) and is_valid(spt_1) and is_valid(spt_2)) else False

    # 3. 成交量 >= 500 張 (500,000 股)
    cond3_volume_ok = (vol_0 >= 500 * 1000) if is_valid(vol_0) else False

    is_hit = cond1_above_easy and cond2_spt_growing and cond3_volume_ok

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F1_筆張現形] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 收盤 > 輕鬆線 : ${close_0:.2f} > ${easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 收盤 > 輕鬆線 : N/A")
        print(f"  [{ '✓' if cond2_spt_growing else '✕' }] 2. 單筆均張遞增 : {spt_0:.2f} > {spt_1:.2f} > {spt_2:.2f}" if is_valid(spt_0) and is_valid(spt_1) and is_valid(spt_2) else "  [✕] 2. 單筆均張遞增 : N/A")
        print(f"  [{ '✓' if cond3_volume_ok else '✕' }] 3. 成交量 >= 500張 : {vol_lots:,.0f} 張")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發筆張現形]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F1_筆張現形',
        '操作建議': '單筆均張連續2日遞增，大戶單筆下單力道強勁，且站上輕鬆線，為典型大戶鎖碼訊號。'
    } if is_hit else {}

    return is_hit, info


# =====================================================================
# F2. 出量上輕
# =====================================================================
def st_qiantang_f2_volume_breakout(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F2_出量上輕】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元
    3. 成交量 >= 350 張 (350,000 股)
    4. 爆量條件 (模式A 或 模式B)：
       - 模式A：昨日量 * 3 且 當日量 >= 3,000 張
       - 模式B：昨日量 * 4.5 且 當日量 < 3,000 張
    """
    profile = profile or {}
    if len(df_single) < 2:
        if verbose:
            print(f"❌ [出量上輕] 資料筆數不足 2 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)
    vol_1 = d1.get('Trading_Volume', None)

    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    mode_a = (vol_0 >= vol_1 * 3.0) and (vol_0 >= 3000 * 1000) if (is_valid(vol_0) and is_valid(vol_1)) else False
    mode_b = (vol_0 >= vol_1 * 4.5) and (vol_0 < 3000 * 1000) if (is_valid(vol_0) and is_valid(vol_1)) else False
    cond4_vol_surge = mode_a or mode_b

    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond4_vol_surge

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_0_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0
        multiple = (vol_0 / vol_1) if (is_valid(vol_0) and is_valid(vol_1) and vol_1 > 0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F2_出量上輕] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 收盤 > 輕鬆線 : ${close_0:.2f} > ${easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 收盤 > 輕鬆線 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_0_lots:,.0f} 張")
        print(f"  [{ '✓' if cond4_vol_surge else '✕' }] 4. 出量爆發 (倍數 {multiple:.1f}x) : 模式A({mode_a}) | 模式B({mode_b})")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發出量上輕]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F2_出量上輕',
        '操作建議': '成交量呈幾何倍數暴增，量能強勢突破並站上輕鬆線，多頭起漲動能極強。'
    } if is_hit else {}

    return is_hit, info


# =====================================================================
# F3. 洗盤後
# =====================================================================
def st_qiantang_f3_after_shakeout(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F3_洗盤後】
    邏輯：
    1. 今日上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元
    3. 成交量 >= 350 張 (350,000 股)
    4. 1日前、2日前或 3日前曾經在輕鬆線之下 (close <= easy_line)，代表洗盤甩轎後重新站回。
    """
    profile = profile or {}
    if len(df_single) < 4:
        if verbose:
            print(f"❌ [洗盤後] 資料筆數不足 4 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]
    d3 = df_single.iloc[-4]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)

    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    was_below_1d = (d1.get('close', 0) <= d1.get('easy_line', 0)) if (is_valid(d1.get('close')) and is_valid(d1.get('easy_line'))) else False
    was_below_2d = (d2.get('close', 0) <= d2.get('easy_line', 0)) if (is_valid(d2.get('close')) and is_valid(d2.get('easy_line'))) else False
    was_below_3d = (d3.get('close', 0) <= d3.get('easy_line', 0)) if (is_valid(d3.get('close')) and is_valid(d3.get('easy_line'))) else False

    cond4_shakeout = was_below_1d or was_below_2d or was_below_3d

    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond4_shakeout

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F3_洗盤後] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 今日上輕鬆 : ${close_0:.2f} > ${easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 今日上輕鬆 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_lots:,.0f} 張")
        print(f"  [{ '✓' if cond4_shakeout else '✕' }] 4. 洗盤甩轎軌跡 : 1日前跌破({was_below_1d}) | 2日前跌破({was_below_2d}) | 3日前跌破({was_below_3d})")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發洗盤後]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F3_洗盤後',
        '操作建議': '短線跌破輕鬆線甩離浮動籌碼後，今日強勢重新站回輕鬆線，洗盤完成轉強。'
    } if is_hit else {}

    return is_hit, info


# =====================================================================
# F4. 強力上
# =====================================================================
def st_qiantang_f4_strong_rise(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F4_強力上】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元
    3. 成交量 >= 350 張 (350,000 股)
    4. 強力起漲：(今日收盤 / 昨日收盤 >= 1.065) 且 (昨日收盤 / 前日收盤 <= 1.06)
    """
    profile = profile or {}
    if len(df_single) < 3:
        if verbose:
            print(f"❌ [強力上] 資料筆數不足 3 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    close_0 = today.get('close', None)
    close_1 = d1.get('close', None)
    close_2 = d2.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)

    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    ratio_0_1 = (close_0 / close_1) if (is_valid(close_0) and is_valid(close_1) and close_1 > 0) else 0.0
    ratio_1_2 = (close_1 / close_2) if (is_valid(close_1) and is_valid(close_2) and close_2 > 0) else 0.0

    cond4_surge_today = ratio_0_1 >= 1.065
    cond5_quiet_yesterday = ratio_1_2 <= 1.060
    cond_strong_rise = cond4_surge_today and cond5_quiet_yesterday

    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond_strong_rise

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F4_強力上] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 上輕鬆 : ${close_0:.2f} > ${easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 上輕鬆 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_lots:,.0f} 張")
        print(f"  [{ '✓' if cond4_surge_today else '✕' }] 4. 今日拉長紅 (>= +6.5%) : {((ratio_0_1 - 1) * 100):+.2f}%")
        print(f"  [{ '✓' if cond5_quiet_yesterday else '✕' }] 5. 昨日未大漲 (<= +6.0%) : {((ratio_1_2 - 1) * 100):+.2f}%")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發強力上]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F4_強力上',
        '操作建議': '昨日平穩沉澱、今日發動攻態拉出長紅，價格具強烈突破攻擊特徵。'
    } if is_hit else {}

    return is_hit, info


# =====================================================================
# F5. 主外上輕
# =====================================================================
def st_qiantang_f5_major_buy_easy(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F5_主外上輕】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元
    3. 成交量 >= 350 張 (350,000 股)
    4. 符合任一籌碼/買超條件：
       - 5天4買 (三大法人 5 日內 4 日淨買超)
       - 6內黃金 (近6日 KD 黃金交叉)
       - 替代基差現形 (SPT 連續遞增 且 MSR >= 12%)
       - 替代主外大買 (Major_Buy >= 1000張 或 Major_Ratio >= 25%)
    """
    profile = profile or {}
    if len(df_single) < 6:
        if verbose:
            print(f"❌ [主外上輕] 資料筆數不足 6 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)

    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    # (A) 5天4買
    if 'net_buy' in df_single.columns:
        last_5 = df_single['net_buy'].tail(5)
        cond_5d_4buy = (last_5 > 0).sum() >= 4
    elif 'Foreign_Investor' in df_single.columns:
        foreign = df_single['Foreign_Investor'].tail(5).fillna(0)
        trust = df_single.get('Investment_Trust', pd.Series(0, index=df_single.index)).tail(5).fillna(0)
        cond_5d_4buy = ((foreign + trust) > 0).sum() >= 4
    else:
        cond_5d_4buy = False

    # (B) 6內黃金
    if 'K' in df_single.columns and 'D' in df_single.columns:
        kd_cross = (df_single['K'] > df_single['D']) & (df_single['K'].shift(1) <= df_single['D'].shift(1))
        cond_6d_gold_cross = kd_cross.tail(6).any()
    else:
        cond_6d_gold_cross = False

    # (C) 替代基差現形 (SPT 連 2 日遞增 且 MSR >= 12%)
    spt_0 = today.get('shares_per_trans', 0)
    spt_1 = d1.get('shares_per_trans', 0)
    spt_2 = d2.get('shares_per_trans', 0)
    spt_growing = (spt_0 > spt_1 > spt_2) if all(map(is_valid, [spt_0, spt_1, spt_2])) else False

    foreign_net = today.get('Foreign_Investor', today.get('foreign_net', 0)) or 0
    trust_net = today.get('Investment_Trust', today.get('trust_net', 0)) or 0
    margin_today = today.get('MarginPurchaseTodayBalance', 0) or 0
    margin_yday = d1.get('MarginPurchaseTodayBalance', 0) or 0
    margin_diff = margin_today - margin_yday

    vol_lots_0 = (vol_0 / 1000.0) if is_valid(vol_0) and vol_0 > 0 else 1.0
    msr = (abs(foreign_net) + abs(trust_net) + abs(margin_diff * 1000)) / vol_0 if (is_valid(vol_0) and vol_0 > 0) else 0.0
    cond_base_diff = spt_growing and (msr >= 0.12)

    # (D) 替代主外大買 (Major_Buy >= 1000張 或 Major_Ratio >= 25%)
    major_buy_shares = foreign_net + trust_net + max(0, margin_diff * 1000)
    major_buy_lots = major_buy_shares / 1000.0
    major_ratio = (major_buy_shares / vol_0) if (is_valid(vol_0) and vol_0 > 0) else 0.0

    cond_major_big_buy = (major_buy_lots >= 1000) or (major_ratio >= 0.25)

    cond4_chip_trigger = cond_5d_4buy or cond_6d_gold_cross or cond_base_diff or cond_major_big_buy

    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond4_chip_trigger

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))

        print("\n" + "=" * 55)
        print(f"🔔 [F5_主外上輕] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 上輕鬆 : ${close_0:.2f} > ${easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 上輕鬆 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_lots_0:,.0f} 張")
        print(f"  [{ '✓' if cond4_chip_trigger else '✕' }] 4. 主外籌碼過關 (滿足任一):")
        print(f"      - 5天4買: {cond_5d_4buy}")
        print(f"      - 6內黃金: {cond_6d_gold_cross}")
        print(f"      - 替代基差現形: {cond_base_diff} (SPT連增:{spt_growing}, MSR:{msr*100:.1f}%)")
        print(f"      - 替代主外大買: {cond_major_big_buy} (買超:{major_buy_lots:,.0f}張, 佔比:{major_ratio*100:.1f}%)")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發主外上輕]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F5_主外上輕',
        '操作建議': '主力與外資法人多頭籌碼集結，搭配技術指標金叉或單筆大單，多方動能明確。'
    } if is_hit else {}

    return is_hit, info


# =====================================================================
# F6. 一朵花
# =====================================================================
def st_qiantang_f6_flower(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F6_一朵花】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元
    3. 成交量 >= 350 張 (350,000 股)
    4. 符合任一強勢爆發條件：
       - 10天7買 (近10天三大法人買超 >= 7天)
       - SPT 爆發 (SPT_t >= MA5(SPT) * 1.5)
       - 替代基數差 >= 40 (VTR >= 1.50 且 MSR >= 25%)
       - 主力外比率 >= 45% (Major_Ratio >= 45%)
       - 替代基數差連4達標 (VTR >= 1.25 且 MSR >= 15% 連續4天)
    """
    profile = profile or {}
    if len(df_single) < 10:
        if verbose:
            print(f"❌ [一朵花] 資料筆數不足 10 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)

    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    # (A) 10天7買
    if 'net_buy' in df_single.columns:
        last_10 = df_single['net_buy'].tail(10)
        cond_10d_7buy = (last_10 > 0).sum() >= 7
    elif 'Foreign_Investor' in df_single.columns:
        foreign = df_single['Foreign_Investor'].tail(10).fillna(0)
        trust = df_single.get('Investment_Trust', pd.Series(0, index=df_single.index)).tail(10).fillna(0)
        cond_10d_7buy = ((foreign + trust) > 0).sum() >= 7
    else:
        cond_10d_7buy = False

    # (B) SPT 爆發 (SPT_t >= MA5(SPT) * 1.5)
    spt_series = df_single['shares_per_trans'] if 'shares_per_trans' in df_single.columns else pd.Series(0, index=df_single.index)
    spt_ma5 = spt_series.rolling(5).mean().iloc[-1] if len(spt_series) >= 5 else 0
    spt_0 = spt_series.iloc[-1]
    cond_spt_surge = (spt_0 >= spt_ma5 * 1.5) if (spt_ma5 > 0) else False

    # 計算 VTR & MSR
    vol_series = df_single['Trading_Volume']
    turnover_series = df_single['Trading_turnover'] if 'Trading_turnover' in df_single.columns else vol_series / 1000.0
    
    vol_ma5 = vol_series.rolling(5).mean().iloc[-1]
    turnover_ma5 = turnover_series.rolling(5).mean().iloc[-1]

    v_ratio = (vol_0 / vol_ma5) if (is_valid(vol_0) and vol_ma5 > 0) else 1.0
    t_ratio = (turnover_series.iloc[-1] / turnover_ma5) if (turnover_series.iloc[-1] > 0 and turnover_ma5 > 0) else 1.0
    vtr_0 = (v_ratio / t_ratio) if (t_ratio > 0) else 1.0

    foreign_net = today.get('Foreign_Investor', today.get('foreign_net', 0)) or 0
    trust_net = today.get('Investment_Trust', today.get('trust_net', 0)) or 0
    margin_diff = (today.get('MarginPurchaseTodayBalance', 0) or 0) - (df_single.iloc[-2].get('MarginPurchaseTodayBalance', 0) or 0)

    msr_0 = (abs(foreign_net) + abs(trust_net) + abs(margin_diff * 1000)) / vol_0 if (is_valid(vol_0) and vol_0 > 0) else 0.0

    # (C) 替代基數差 >= 40 (VTR >= 1.50 且 MSR >= 25%)
    cond_base_40 = (vtr_0 >= 1.50) and (msr_0 >= 0.25)

    # (D) 主力外比率 >= 45%
    major_buy_shares = foreign_net + trust_net + max(0, margin_diff * 1000)
    major_ratio = (major_buy_shares / vol_0) if (is_valid(vol_0) and vol_0 > 0) else 0.0
    cond_major_45 = major_ratio >= 0.45

    # (E) 替代基數差連 4 日達標 (VTR >= 1.25 且 MSR >= 15% 連續 4 天)
    cond_base_4d = False
    if len(df_single) >= 4:
        vtr_4d_ok = True
        for i in range(-4, 0):
            row_i = df_single.iloc[i]
            row_prev = df_single.iloc[i-1] if (len(df_single) + i - 1) >= 0 else row_i
            v_i = row_i.get('Trading_Volume', 0)
            f_i = row_i.get('Foreign_Investor', row_i.get('foreign_net', 0)) or 0
            t_i = row_i.get('Investment_Trust', row_i.get('trust_net', 0)) or 0
            m_diff_i = (row_i.get('MarginPurchaseTodayBalance', 0) or 0) - (row_prev.get('MarginPurchaseTodayBalance', 0) or 0)
            msr_i = (abs(f_i) + abs(t_i) + abs(m_diff_i * 1000)) / v_i if v_i > 0 else 0
            if msr_i < 0.15:
                vtr_4d_ok = False
                break
        cond_base_4d = vtr_4d_ok

    cond4_flower_trigger = cond_10d_7buy or cond_spt_surge or cond_base_40 or cond_major_45 or cond_base_4d

    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond4_flower_trigger

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F6_一朵花] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 上輕鬆 : ${close_0:.2f} > ${easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 上輕鬆 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_lots:,.0f} 張")
        print(f"  [{ '✓' if cond4_flower_trigger else '✕' }] 4. 一朵花爆發條件 (滿足任一):")
        print(f"      - 10天7買: {cond_10d_7buy}")
        print(f"      - SPT爆發 (>=1.5x MA5): {cond_spt_surge} (SPT:{spt_0:.2f}, MA5:{spt_ma5:.2f})")
        print(f"      - 替代基數差>=40: {cond_base_40} (VTR:{vtr_0:.2f}, MSR:{msr_0*100:.1f}%)")
        print(f"      - 主力外比率>=45%: {cond_major_45} ({major_ratio*100:.1f}%)")
        print(f"      - 替代基數差連4達標: {cond_base_4d}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發一朵花]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F6_一朵花',
        '操作建議': '法人集中度高且大單急敲，呈現強烈籌碼與量能錦上添花之起漲型態。'
    } if is_hit else {}

    return is_hit, info


# =====================================================================
# F7. 飆股
# =====================================================================
def st_qiantang_f7_super_stock(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F7_飆股】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元
    3. 成交量 >= 350 張 (350,000 股)
    4. 飆股型態條件 (滿足任一組合)：
       - (替代基差現形 且 (替代主外大買 或 Major_Ratio >= 33%))
       - 替代 38 全 (近 3 日集中度 >= 15% 且 近 8 日集中度 >= 10%)
       - (替代基數差 >= 16 且 替代主外 1600 張)
    """
    profile = profile or {}
    if len(df_single) < 8:
        if verbose:
            print(f"❌ [飆股] 資料筆數不足 8 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)

    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    # 籌碼基礎變數計算
    foreign_net = today.get('Foreign_Investor', today.get('foreign_net', 0)) or 0
    trust_net = today.get('Investment_Trust', today.get('trust_net', 0)) or 0
    margin_diff = (today.get('MarginPurchaseTodayBalance', 0) or 0) - (d1.get('MarginPurchaseTodayBalance', 0) or 0)

    spt_0 = today.get('shares_per_trans', 0)
    spt_1 = d1.get('shares_per_trans', 0)
    spt_2 = d2.get('shares_per_trans', 0)
    spt_growing = (spt_0 > spt_1 > spt_2) if all(map(is_valid, [spt_0, spt_1, spt_2])) else False

    msr_0 = (abs(foreign_net) + abs(trust_net) + abs(margin_diff * 1000)) / vol_0 if (is_valid(vol_0) and vol_0 > 0) else 0.0
    cond_base_diff = spt_growing and (msr_0 >= 0.12)

    major_buy_shares = foreign_net + trust_net + max(0, margin_diff * 1000)
    major_buy_lots = major_buy_shares / 1000.0
    major_ratio = (major_buy_shares / vol_0) if (is_valid(vol_0) and vol_0 > 0) else 0.0

    cond_major_big = (major_buy_lots >= 1000) or (major_ratio >= 0.25)
    cond_combo_1 = cond_base_diff and (cond_major_big or major_ratio >= 0.33)

    # 組合 2: 替代 38 全 (近 3 日集中度 >= 15% 且 近 8 日集中度 >= 10%)
    last_3_vol = df_single['Trading_Volume'].tail(3).sum()
    last_8_vol = df_single['Trading_Volume'].tail(8).sum()

    f_3 = df_single.get('Foreign_Investor', df_single.get('foreign_net', pd.Series(0, index=df_single.index))).tail(3).sum()
    t_3 = df_single.get('Investment_Trust', df_single.get('trust_net', pd.Series(0, index=df_single.index))).tail(3).sum()
    m_3 = (df_single['MarginPurchaseTodayBalance'].iloc[-1] - df_single['MarginPurchaseTodayBalance'].iloc[-4]) * 1000 if ('MarginPurchaseTodayBalance' in df_single.columns and len(df_single) >= 4) else 0

    f_8 = df_single.get('Foreign_Investor', df_single.get('foreign_net', pd.Series(0, index=df_single.index))).tail(8).sum()
    t_8 = df_single.get('Investment_Trust', df_single.get('trust_net', pd.Series(0, index=df_single.index))).tail(8).sum()
    m_8 = (df_single['MarginPurchaseTodayBalance'].iloc[-1] - df_single['MarginPurchaseTodayBalance'].iloc[-9]) * 1000 if ('MarginPurchaseTodayBalance' in df_single.columns and len(df_single) >= 9) else 0

    conc_3d = ((f_3 + t_3 + max(0, m_3)) / last_3_vol) if last_3_vol > 0 else 0.0
    conc_8d = ((f_8 + t_8 + max(0, m_8)) / last_8_vol) if last_8_vol > 0 else 0.0

    cond_combo_2 = (conc_3d >= 0.15) and (conc_8d >= 0.10)

    # 組合 3: (替代基數差 >= 16 且 替代主外 1600張)
    vol_series = df_single['Trading_Volume']
    turnover_series = df_single['Trading_turnover'] if 'Trading_turnover' in df_single.columns else vol_series / 1000.0
    vol_ma5 = vol_series.rolling(5).mean().iloc[-1]
    turnover_ma5 = turnover_series.rolling(5).mean().iloc[-1]

    v_ratio = (vol_0 / vol_ma5) if (is_valid(vol_0) and vol_ma5 > 0) else 1.0
    t_ratio = (turnover_series.iloc[-1] / turnover_ma5) if (turnover_series.iloc[-1] > 0 and turnover_ma5 > 0) else 1.0
    vtr_0 = (v_ratio / t_ratio) if (t_ratio > 0) else 1.0

    cond_base_16 = (vtr_0 >= 1.25) and (msr_0 >= 0.15)
    cond_major_1600 = major_buy_lots >= 1600.0

    cond_combo_3 = cond_base_16 and cond_major_1600

    cond4_super_stock_trigger = cond_combo_1 or cond_combo_2 or cond_combo_3

    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond4_super_stock_trigger

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F7_飆股] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 上輕鬆 : ${close_0:.2f} > ${easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 上輕鬆 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_lots:,.0f} 張")
        print(f"  [{ '✓' if cond4_super_stock_trigger else '✕' }] 4. 飆股條件組合 (滿足任一組合):")
        print(f"      - 組合1 (基差現形+主外大買/比率>=33%): {cond_combo_1}")
        print(f"      - 組合2 (替代38全 - 近3日:{conc_3d*100:.1f}%, 近8日:{conc_8d*100:.1f}%): {cond_combo_2}")
        print(f"      - 組合3 (基數差>=16 且 主外>=1600張 - 買超:{major_buy_lots:,.0f}張): {cond_combo_3}")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發飆股]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F7_飆股',
        '操作建議': '籌碼極度高度集中，內外資法人大舉連買卡位，具備強烈黑馬飆股特徵。'
    } if is_hit else {}

    return is_hit, info
