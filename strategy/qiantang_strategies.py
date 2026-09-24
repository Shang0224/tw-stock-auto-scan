# qiantang_strategies.py
"""
錢塘潮選股系統 - 多方選股策略庫 (qiantang_strategies.py)
說明：本模組收錄錢塘潮 7 大多方選股公式，統一採用 `st_` 前綴命名，
並符合 engine.py 策略呼叫簽名 `st_func(df_single, profile=None) -> tuple[bool, dict]`。
"""

import pandas as pd
import numpy as np


def is_valid(val):
    """檢查數值是否有效 (非 None 且非 NaN)"""
    return val is not None and pd.notna(val)


def _check_basic_pass(today_row) -> bool:
    """
    錢塘潮選股基礎通行證：
    1. 收盤價 > 輕鬆線 (close > easy_line)
    2. 收盤價 >= 5 元 (close >= 5.0)
    """
    close = today_row.get("close", 0)
    easy = today_row.get("easy_line", 0)
    if not (is_valid(close) and is_valid(easy)):
        return False
    return (close > easy) and (close >= 5.0)


# =========================================================================
# 1. 【筆張現形】 (f1_spt_growth)
# =========================================================================
def st_qiantang_f1_spt_growth(
    df_single: pd.DataFrame, profile: dict = None
) -> tuple[bool, dict]:
    """
    【筆張現形】
    核心邏輯：
    1. 基礎通行證：上輕鬆線 且 收盤價 >= 5 元
    2. 成交量門檻：成交量 >= 500 張 (500,000 股)
    3. 單筆均張 (SPT) 連續 2 日遞增 (SPT_t > SPT_{t-1} > SPT_{t-2})
    """
    if len(df_single) < 3:
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    if not _check_basic_pass(today):
        return False, {}

    vol_0 = today.get("Trading_Volume", 0)
    cond_vol = (vol_0 >= 500 * 1000) if is_valid(vol_0) else False

    # 優先取用預處理算好的單筆均張 (shares_per_trans)
    spt_0 = today.get("shares_per_trans", None)
    spt_1 = d1.get("shares_per_trans", None)
    spt_2 = d2.get("shares_per_trans", None)

    # 備援：若欄位缺失，現場動態推算 (Volume / turnover)
    if not all(map(is_valid, [spt_0, spt_1, spt_2])):
        turn_0 = today.get("Trading_turnover", 0)
        turn_1 = d1.get("Trading_turnover", 0)
        turn_2 = d2.get("Trading_turnover", 0)
        spt_0 = (vol_0 / turn_0) if is_valid(turn_0) and turn_0 > 0 else 0
        spt_1 = (d1.get("Trading_Volume", 0) / turn_1) if is_valid(turn_1) and turn_1 > 0 else 0
        spt_2 = (d2.get("Trading_Volume", 0) / turn_2) if is_valid(turn_2) and turn_2 > 0 else 0

    cond_spt_growing = (spt_0 > spt_1 > spt_2) if all(map(is_valid, [spt_0, spt_1, spt_2])) else False

    is_hit = cond_vol and cond_spt_growing

    info = {
        "選股公式": "筆張現形",
        "操作建議": f"單筆均張連2日遞增 ({spt_0:.2f} > {spt_1:.2f} > {spt_2:.2f})，大戶單筆下單力道增強，鎖碼意圖明顯。",
        "成交量(張)": int(vol_0 / 1000) if is_valid(vol_0) else 0,
    } if is_hit else {}

    return is_hit, info


# =========================================================================
# 2. 【出量上輕】 (f2_volume_breakout)
# =========================================================================
def st_qiantang_f2_volume_breakout(
    df_single: pd.DataFrame, profile: dict = None
) -> tuple[bool, dict]:
    """
    【出量上輕】
    核心邏輯：
    1. 基礎通行證：上輕鬆線 且 收盤價 >= 5 元
    2. 成交量門檻：當日成交量 >= 350 張 (350,000 股)
    3. 量能爆發雙軌門檻：
       - 模式 A：今日成交量 >= 昨日成交量 * 3.0 且 今日成交量 >= 3,000 張
       - 模式 B：今日成交量 >= 昨日成交量 * 4.5 且 今日成交量 < 3,000 張
    """
    if len(df_single) < 2:
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]

    if not _check_basic_pass(today):
        return False, {}

    v0 = today.get("Trading_Volume", 0)
    v1 = d1.get("Trading_Volume", 0)

    if not (is_valid(v0) and is_valid(v1) and v1 > 0):
        return False, {}

    cond_vol_min = (v0 >= 350 * 1000)

    mode_a = (v0 >= v1 * 3.0) and (v0 >= 3000 * 1000)
    mode_b = (v0 >= v1 * 4.5) and (v0 < 3000 * 1000)

    is_hit = cond_vol_min and (mode_a or mode_b)

    multiple = v0 / v1 if v1 > 0 else 0
    info = {
        "選股公式": "出量上輕",
        "操作建議": f"量能劇烈放大 (今日量 {v0/1000:,.0f} 張，為昨日 {multiple:.1f} 倍)，突破盤整啟動強攻。",
        "成交量(張)": int(v0 / 1000),
    } if is_hit else {}

    return is_hit, info


# =========================================================================
# 3. 【洗盤後】 (f3_after_shakeout)
# =========================================================================
def st_qiantang_f3_after_shakeout(
    df_single: pd.DataFrame, profile: dict = None
) -> tuple[bool, dict]:
    """
    【洗盤後】
    核心邏輯：
    1. 基礎通行證：今日收盤 > 今日輕鬆線 且 收盤價 >= 5 元
    2. 成交量門檻：今日成交量 >= 350 張 (350,000 股)
    3. 洗盤軌跡：近 1~3 日內 (昨日、前日或大前天) 曾落於輕鬆線之下 (close <= easy_line)
    """
    if len(df_single) < 4:
        return False, {}

    today = df_single.iloc[-1]

    if not _check_basic_pass(today):
        return False, {}

    v0 = today.get("Trading_Volume", 0)
    cond_vol = (v0 >= 350 * 1000) if is_valid(v0) else False

    # 檢視倒數第 2, 3, 4 筆 (昨日、前日、大前天)
    d1_close, d1_easy = df_single.iloc[-2].get("close", 0), df_single.iloc[-2].get("easy_line", 0)
    d2_close, d2_easy = df_single.iloc[-3].get("close", 0), df_single.iloc[-3].get("easy_line", 0)
    d3_close, d3_easy = df_single.iloc[-4].get("close", 0), df_single.iloc[-4].get("easy_line", 0)

    was_below_1d = (d1_close <= d1_easy) if (is_valid(d1_close) and is_valid(d1_easy)) else False
    was_below_2d = (d2_close <= d2_easy) if (is_valid(d2_close) and is_valid(d2_easy)) else False
    was_below_3d = (d3_close <= d3_easy) if (is_valid(d3_close) and is_valid(d3_easy)) else False

    cond_shakeout = was_below_1d or was_below_2d or was_below_3d

    is_hit = cond_vol and cond_shakeout

    info = {
        "選股公式": "洗盤後",
        "操作建議": "近 3 日內曾跌破輕鬆線完成洗盤甩轎，今日帶量強勢重新站回輕鬆線，啟動攻擊波。",
        "成交量(張)": int(v0 / 1000) if is_valid(v0) else 0,
    } if is_hit else {}

    return is_hit, info


# =========================================================================
# 4. 【強力上】 (f4_strong_rise)
# =========================================================================
def st_qiantang_f4_strong_rise(
    df_single: pd.DataFrame, profile: dict = None
) -> tuple[bool, dict]:
    """
    【強力上】
    核心邏輯：
    1. 基礎通行證：上輕鬆線 且 收盤價 >= 5 元
    2. 成交量門檻：當日成交量 >= 350 張 (350,000 股)
    3. 漲幅爆發力組合：
       - 今日漲幅 >= 6.5% (今日收盤 / 昨日收盤 >= 1.065)
       - 昨日漲幅 <= 6.0% (昨日收盤 / 前日收盤 <= 1.060，即昨日蓄勢未暴漲)
    """
    if len(df_single) < 3:
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    if not _check_basic_pass(today):
        return False, {}

    c0 = today.get("close", 0)
    c1 = d1.get("close", 0)
    c2 = d2.get("close", 0)
    v0 = today.get("Trading_Volume", 0)

    if not (all(map(is_valid, [c0, c1, c2, v0])) and c1 > 0 and c2 > 0):
        return False, {}

    cond_vol = (v0 >= 350 * 1000)
    cond_today_surge = (c0 / c1 >= 1.065)
    cond_yday_stable = (c1 / c2 <= 1.060)

    is_hit = cond_vol and cond_today_surge and cond_yday_stable

    today_pct = ((c0 / c1) - 1) * 100
    info = {
        "選股公式": "強力上",
        "操作建議": f"昨日平穩整理後，今日長紅爆發強漲 ({today_pct:.1f}%)，突破上攻力道強勁。",
        "成交量(張)": int(v0 / 1000),
    } if is_hit else {}

    return is_hit, info

# =========================================================================
# 5. 【主外上輕】 (f5_major_buy_easy)
# =========================================================================
def st_qiantang_f5_major_buy_easy(
    df_single: pd.DataFrame, profile: dict = None
) -> tuple[bool, dict]:
    """
    【主外上輕】
    核心邏輯：
    1. 基礎通行證：上輕鬆線 且 收盤價 >= 5 元 且 當日成交量 >= 350 張
    2. 籌碼/動能 5 選 1 觸發條件：
       - (1) 5天4買：近 5 日三大法人/主力買超有 4 日為正
       - (2) 6內黃金：近 6 日內發生過 KD 黃金交叉
       - (3) 7內2/張：單筆均張連 2 日遞增 (同筆張現形)
       - (4) 替代基差現形：SPT 連續 2 日遞增 且 主力成交佔比 (MSR) >= 12%
       - (5) 替代主外大買：替代主外買超 (Major_Buy) >= 1,000 張 或 主力外比率 (Major_Ratio) >= 25%
    """
    if len(df_single) < 6:
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    if not _check_basic_pass(today):
        return False, {}

    v0 = today.get("Trading_Volume", 0)
    if not (is_valid(v0) and v0 >= 350 * 1000):
        return False, {}

    # 1. 5天4買判定
    if "net_buy" in df_single.columns:
        last_5_buy = df_single["net_buy"].tail(5)
        cond_5d4buy = (last_5_buy > 0).sum() >= 4
    elif "major_buy" in df_single.columns:
        last_5_buy = df_single["major_buy"].tail(5)
        cond_5d4buy = (last_5_buy > 0).sum() >= 4
    else:
        cond_5d4buy = False

    # 2. 6日內 KD 黃金交叉判定
    if "K" in df_single.columns and "D" in df_single.columns:
        kd_cross_series = (df_single["K"] > df_single["D"]) & (df_single["K"].shift(1) <= df_single["D"].shift(1))
        cond_kd_gold_6d = bool(kd_cross_series.tail(6).any())
    else:
        cond_kd_gold_6d = False

    # 3. 筆張現形遞態 (SPT 0 > 1 > 2)
    spt_0 = today.get("shares_per_trans", 0)
    spt_1 = d1.get("shares_per_trans", 0)
    spt_2 = d2.get("shares_per_trans", 0)
    cond_spt_growing = (spt_0 > spt_1 > spt_2) if all(map(is_valid, [spt_0, spt_1, spt_2])) else False

    # 4. 替代基差現形 (SPT 遞增 + MSR >= 12%)
    msr_0 = today.get("msr", 0)
    cond_alt_basis = cond_spt_growing and (msr_0 >= 0.12) if is_valid(msr_0) else False

    # 5. 替代主外大買 (Major_Buy >= 1000張 或 Major_Ratio >= 25%)
    mb_0 = today.get("major_buy", 0)
    mr_0 = today.get("major_ratio", 0)
    cond_alt_major_big_buy = (
        (mb_0 >= 1000 * 1000) or (mr_0 >= 0.25)
    ) if (is_valid(mb_0) and is_valid(mr_0)) else False

    is_hit = cond_5d4buy or cond_kd_gold_6d or cond_spt_growing or cond_alt_basis or cond_alt_major_big_buy

    info = {
        "選股公式": "主外上輕",
        "操作建議": "籌碼多頭排列，包含法人強買/大戶進駐/技術金叉特徵，隨時啟動攻擊。",
        "成交量(張)": int(v0 / 1000),
    } if is_hit else {}

    return is_hit, info


# =========================================================================
# 6. 【一朵花】 (f6_flower)
# =========================================================================
def st_qiantang_f6_flower(
    df_single: pd.DataFrame, profile: dict = None
) -> tuple[bool, dict]:
    """
    【一朵花】
    核心邏輯：
    1. 基礎通行證：上輕鬆線 且 收盤價 >= 5 元 且 當日成交量 >= 350 張
    2. 籌碼爆發 5 選 1 觸發條件：
       - (1) 10天7買：近 10 日內有 7 日以上法人買超
       - (2) 2倍筆數：今日 SPT >= 近 5 日 SPT 均值 (MA5_SPT) 的 1.5 倍
       - (3) 替代基數差 >= 40：量筆放大比率 (VTR) >= 1.50 且 主力成交佔比 (MSR) >= 25%
       - (4) 主力外比率 >= 45%：Major_Ratio >= 0.45
       - (5) 替代基數差連續4日達標：近 4 日每日均滿足 (VTR >= 1.25 且 MSR >= 15%)
    """
    if len(df_single) < 10:
        return False, {}

    today = df_single.iloc[-1]

    if not _check_basic_pass(today):
        return False, {}

    v0 = today.get("Trading_Volume", 0)
    if not (is_valid(v0) and v0 >= 350 * 1000):
        return False, {}

    # 1. 10天7買判定
    if "net_buy" in df_single.columns:
        last_10_buy = df_single["net_buy"].tail(10)
        cond_10d7buy = (last_10_buy > 0).sum() >= 7
    elif "major_buy" in df_single.columns:
        last_10_buy = df_single["major_buy"].tail(10)
        cond_10d7buy = (last_10_buy > 0).sum() >= 7
    else:
        cond_10d7buy = False

    # 2. SPT 放大 1.5 倍 (SPT >= 1.5 * MA5_SPT)
    spt_0 = today.get("shares_per_trans", 0)
    spt_ma5 = df_single["shares_per_trans"].tail(5).mean() if "shares_per_trans" in df_single.columns else 0
    cond_spt_surge = (spt_0 >= spt_ma5 * 1.5) if (is_valid(spt_0) and is_valid(spt_ma5) and spt_ma5 > 0) else False

    # 3. 替代基數差 >= 40 (VTR >= 1.50 且 MSR >= 25%)
    vtr_0 = today.get("vtr", 0)
    msr_0 = today.get("msr", 0)
    cond_alt_diff_40 = (vtr_0 >= 1.50 and msr_0 >= 0.25) if (is_valid(vtr_0) and is_valid(msr_0)) else False

    # 4. 主力外比率 >= 45% (Major_Ratio >= 0.45)
    mr_0 = today.get("major_ratio", 0)
    cond_major_ratio_45 = (mr_0 >= 0.45) if is_valid(mr_0) else False

    # 5. 替代基數差連續 4 日達標 (VTR >= 1.25 且 MSR >= 15%)
    if "vtr" in df_single.columns and "msr" in df_single.columns:
        vtr_tail4 = df_single["vtr"].tail(4)
        msr_tail4 = df_single["msr"].tail(4)
        cond_alt_diff_4d = bool(((vtr_tail4 >= 1.25) & (msr_tail4 >= 0.15)).all()) if len(vtr_tail4) == 4 else False
    else:
        cond_alt_diff_4d = False

    is_hit = cond_10d7buy or cond_spt_surge or cond_alt_diff_40 or cond_major_ratio_45 or cond_alt_diff_4d

    info = {
        "選股公式": "一朵花",
        "操作建議": "籌碼極度集中，主力大單急進鎖碼，呈現一朵花盛開之極強起漲訊號。",
        "成交量(張)": int(v0 / 1000),
    } if is_hit else {}

    return is_hit, info


# =========================================================================
# 7. 【飆股】 (f7_super_stock)
# =========================================================================
def st_qiantang_f7_super_stock(
    df_single: pd.DataFrame, profile: dict = None
) -> tuple[bool, dict]:
    """
    【飆股】
    核心邏輯：
    1. 基礎通行證：上輕鬆線 且 收盤價 >= 5 元 且 當日成交量 >= 350 張
    2. 飆股組合 3 選 1 觸發條件：
       - (1) 組合 A：替代基差現形 (SPT連2遞增 + MSR>=12%) 且 (替代主外大買 或 Major_Ratio >= 33%)
       - (2) 組合 B：替代 38 全 (近 3 日籌碼集中度 >= 15% 且 近 8 日籌碼集中度 >= 10%)
       - (3) 組合 C：替代基數差 >= 16 (VTR >= 1.25 且 MSR >= 15%) 且 替代主外 1600 (Major_Buy >= 1,600 張)
    """
    if len(df_single) < 8:
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    if not _check_basic_pass(today):
        return False, {}

    v0 = today.get("Trading_Volume", 0)
    if not (is_valid(v0) and v0 >= 350 * 1000):
        return False, {}

    # 基礎參數讀取
    spt_0, spt_1, spt_2 = today.get("shares_per_trans", 0), d1.get("shares_per_trans", 0), d2.get("shares_per_trans", 0)
    msr_0 = today.get("msr", 0)
    mb_0 = today.get("major_buy", 0)
    mr_0 = today.get("major_ratio", 0)
    vtr_0 = today.get("vtr", 0)

    # 1. 替代基差現形
    cond_spt_growing = (spt_0 > spt_1 > spt_2) if all(map(is_valid, [spt_0, spt_1, spt_2])) else False
    cond_alt_basis = cond_spt_growing and (msr_0 >= 0.12) if is_valid(msr_0) else False

    # 替代主外大買
    cond_alt_major_big_buy = ((mb_0 >= 1000 * 1000) or (mr_0 >= 0.25)) if (is_valid(mb_0) and is_valid(mr_0)) else False

    # 組合 A 判斷
    mode_a = cond_alt_basis and (cond_alt_major_big_buy or (mr_0 >= 0.33)) if is_valid(mr_0) else False

    # 2. 組合 B：替代 38 全 (近 3 日籌碼集中度 >= 15% 且 近 8 日集中度 >= 10%)
    if "major_buy" in df_single.columns and "Trading_Volume" in df_single.columns:
        mb_3d = df_single["major_buy"].tail(3).sum()
        vol_3d = df_single["Trading_Volume"].tail(3).sum()
        conc_3d = (mb_3d / vol_3d) if (vol_3d > 0) else 0

        mb_8d = df_single["major_buy"].tail(8).sum()
        vol_8d = df_single["Trading_Volume"].tail(8).sum()
        conc_8d = (mb_8d / vol_8d) if (vol_8d > 0) else 0

        mode_b = (conc_3d >= 0.15) and (conc_8d >= 0.10)
    else:
        mode_b = False

    # 3. 組合 C：(替代基數差 >= 16) 且 (替代主外 1600)
    cond_alt_diff_16 = (vtr_0 >= 1.25 and msr_0 >= 0.15) if (is_valid(vtr_0) and is_valid(msr_0)) else False
    cond_major_1600 = (mb_0 >= 1600 * 1000) if is_valid(mb_0) else False
    mode_c = cond_alt_diff_16 and cond_major_1600

    is_hit = mode_a or mode_b or mode_c

    info = {
        "選股公式": "飆股",
        "操作建議": "籌碼多重指標同步重暴疊達標，符合超級主升段飆股起漲特徵。",
        "成交量(張)": int(v0 / 1000),
    } if is_hit else {}

    return is_hit, info


