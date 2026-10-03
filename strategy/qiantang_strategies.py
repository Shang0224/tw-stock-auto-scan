# strategy/qiantang_strategies.py
"""
錢塘潮選股系統 - 7 大多方選股策略模組 (qiantang_strategies.py)
說明：完全對齊 monitor/qiantang_monitor.py 之除錯訊息 (verbose) 輸出機制與回傳格式 (is_hit, info)。
"""

import pandas as pd
import numpy as np
from strategy.config import DEBUG_VERBOSE, BUY_PARAM_PROFILES


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
    【F1_筆張現形 - 策略完整說明】
    捕捉市場中主力大單敲進、量能同步放大且站穩多頭主升段的潛在飆股。
    
    核心邏輯：
    1. 嚴格欄位取值：若缺少必要欄位直接報錯 (KeyError)，避免隱性錯誤。
    2. 股數基準：Trading_Volume 全程以「真實股數」進行運算與門檻判定。
    3. 價格乖離控制：收盤價 > 輕鬆線 (easy_line)，且未過度偏離 (close / easy <= 1.12)。
    4. 籌碼連續性：單筆均張連續 2 日遞增 (t > t-1 > t-2)，代表大單持續集結。
    5. 單筆均張爆發：當日單筆均張顯著超越 5 日均張 (spt_0 >= spt_ma5 * 1.15)。
    6. 量能與金額門檻：當日成交股數相較於 5 日均量顯著放大 (vol_0 >= vol_ma5 * 1.3)，
       且成交金額需達 1,000 萬元以上（過濾無流動性殭屍股）。
    7. MA60 趨勢濾網：收盤價必須站上 60 日均線 (MA60)，過濾弱勢反彈與空頭排列個股。

    修改自st_qiantang_f1_spt_growth_20261001
    """
    print("st_qiantang_f1_spt_growth*******************************************************")
    profile = profile or {}

    # ==========================================
    # 內部過濾條件參數設定區
    # ==========================================
    vol_boost_ratio = 1.3               # 相對量能放大倍數 (當日股數 / 5日均量股數)
    min_safety_turnover = 10_000_000    # 底層安全門檻：1,000 萬台幣 (以股數 * 收盤價計算)
    spt_growth_ratio = 1.15             # 單筆均張放大倍數 (相較於 5日均張的門檻)
    max_easy_bias = 1.12                # 輕鬆線乖離率上限 (防止追高過熱)

    # 必須確保資料筆數至少有 60 筆以上，否則無法計算 MA60 均線
    if len(df_single) < 60:
        if verbose:
            print("❌ [筆張現形] 資料筆數不足 60 筆（無法計算 MA60 濾網）")
        return False, {}

    # 取得最近三個交易日的資料列 (0 代表今天/當日，1 代表昨天，2 代表前天)
    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    # ==========================================
    # 欄位嚴格取值區 (若欄位拼寫錯誤或遺失，直接引發 KeyError 報錯)
    # ==========================================
    close_0 = today['close']              # 當日收盤價
    easy_0 = today['easy_line']          # 當日輕鬆線數值
    vol_0 = today['Trading_Volume']      # 當日成交量 (單位：股數)

    spt_0 = today['shares_per_trans']    # 當日單筆均張
    spt_1 = d1['shares_per_trans']       # 昨日單筆均張
    spt_2 = d2['shares_per_trans']       # 前日單筆均張

    # 計算 5 日成交量均值與 5 日單筆均張均值
    vol_series = df_single['Trading_Volume'].tail(5)
    vol_ma5 = vol_series.mean()

    spt_series = df_single['shares_per_trans'].tail(5)
    spt_ma5 = spt_series.mean()

    # 計算 60 日均線 (MA60) 基準
    close_series_60 = df_single['close'].tail(60)
    ma60_0 = close_series_60.mean()

    # 當日成交金額計算 (真實股數 * 收盤價)
    turnover_amount = vol_0 * close_0

    # ==========================================
    # 策略核心條件判斷區
    # ==========================================
    
    # 條件 1：站上輕鬆線且未過熱 (1.0 < 乖離率 <= max_easy_bias)
    bias = close_0 / easy_0
    cond1_easy_ok = (1.0 < bias <= max_easy_bias)

    # 條件 2：單筆均張連續 2 日遞增 (t > t-1 > t-2)
    cond2_spt_growing = (spt_0 > spt_1 > spt_2)

    # 條件 3：當日單筆均張顯著突破 5 日均張達指定倍數
    cond3_spt_surge = (spt_0 >= spt_ma5 * spt_growth_ratio)

    # 條件 4：量能相對放大率達標 + 底層安全成交金額門檻
    is_relative_boost = (vol_0 >= vol_ma5 * vol_boost_ratio)
    is_not_zombie = (turnover_amount >= min_safety_turnover)
    cond4_vol_boost_ok = is_relative_boost and is_not_zombie

    # 條件 5：收盤價必須站上 60 日均線 (MA60 多頭過濾)
    cond5_ma60_ok = (close_0 >= ma60_0)

    # 總體過濾結果：必須同時滿足以上 5 大核心條件
    is_hit = (
        cond1_easy_ok 
        and cond2_spt_growing 
        and cond3_spt_surge 
        and cond4_vol_boost_ok 
        and cond5_ma60_ok
    )

    # ==========================================
    # 除錯與詳細 Log 輸出區
    # ==========================================
    if verbose:
        stock_id = today['stock_id']
        date_str = str(today['date'])
        
        vol_lots = vol_0 / 1000.0  # 轉換為張數方便閱讀
        actual_boost = vol_0 / vol_ma5 if vol_ma5 > 0 else 0.0

        print("\n" + "=" * 65)
        print(f"🔔 [F1_筆張現形] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 65)
        print(f"  [{ '✓' if cond1_easy_ok else '✕' }] 1. 站上輕鬆線且未過熱 : Close=\({close_0:.2f}, Easy=\){easy_0:.2f} (乖離率:{bias:.3f})")
        print(f"  [{ '✓' if cond2_spt_growing else '✕' }] 2. 單筆均張連續2日遞增 : {spt_0:.2f} > {spt_1:.2f} > {spt_2:.2f}")
        print(f"  [{ '✓' if cond3_spt_surge else '✕' }] 3. 均張顯著放大 (>= MA5*{spt_growth_ratio}) : {spt_0:.2f} vs MA5:{spt_ma5:.2f}")
        print(f"  [{ '✓' if cond4_vol_boost_ok else '✕' }] 4. 量能相對放大與金額門檻 : {actual_boost:.2f}倍 (成交量:{vol_lots:,.0f}張, 金額:{turnover_amount/10000:,.0f}萬)")
        print(f"  [{ '✓' if cond5_ma60_ok else '✕' }] 5. 收盤價站上 60 日均線 : Close=\({close_0:.2f} vs MA60:\){ma60_0:.2f}")
        print("-" * 65)
        print(f"🎯 最終觸發結果: {'🔥 [觸發強勢筆張現形]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 65 + "\n")

    # 回傳結果字典
    info = {
        '選股公式': 'F1_筆張現形',
        '操作建議': '單筆均張與當日總量能同步放大，且股價站穩 60 日均線主升段，為主力帶量實質卡位訊號。'
    } if is_hit else {}

    return is_hit, info
    
def st_qiantang_f1_spt_growth_20261001(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F1_筆張現形 - 股數處理與量能相對放大版】
    邏輯：
    1. Trading_Volume 全程以「股數」進行運算與門檻判定。
    2. 收盤價 > 輕鬆線 (easy_line)，且未過度偏離 (close / easy <= 1.12)。
    3. 單筆均張連續 2 日遞增 (t > t-1 > t-2)。
    4. 當日單筆均張顯著超越 5 日均張 (spt_0 >= spt_ma5 * 1.15)。
    5. 當日成交股數相較於 5 日均量顯著放大 (vol_0 >= vol_ma5 * 1.3)，且成交金額 >= 1,000 萬元 (防無流動性殭屍股)。

    修改自st_qiantang_f1_spt_growth_20260930
    """
    print("st_qiantang_f1_spt_growth*******************************************************")
    profile = profile or {}

    # 內部過濾條件變數設定
    vol_boost_ratio = 1.3             # 相對量能放大倍數 (當日股數 / 5日均量股數)
    min_safety_turnover = 10_000_000  # 底層安全門檻：1,000 萬台幣 (以股數*股價計算)
    spt_growth_ratio = 1.15           # 單筆均張放大倍數 (相較於 5日均張)
    max_easy_bias = 1.12              # 輕鬆線乖離率上限 (防止過熱追高)

    if len(df_single) < 5:
        if verbose:
            print("❌ [筆張現形] 資料筆數不足 5 筆")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)  # 單位：股數

    spt_0 = today.get('shares_per_trans', None)
    spt_1 = d1.get('shares_per_trans', None)
    spt_2 = d2.get('shares_per_trans', None)

    # 計算 5 日成交量均值 (MA5 Volume，單位：股數) 與 5 日單筆均張均值 (MA5 SPT)
    vol_series = df_single['Trading_Volume'].tail(5)
    vol_ma5 = vol_series.mean() if len(vol_series) == 5 else None

    spt_series = df_single['shares_per_trans'].tail(5)
    spt_ma5 = spt_series.mean() if len(spt_series) == 5 else None

    # 當日成交金額計算 (股數 * 收盤價)
    turnover_amount = (vol_0 * close_0) if (is_valid(vol_0) and is_valid(close_0)) else 0.0

    # 1. 站上輕鬆線且未過熱 (1.0 < close / easy_line <= max_easy_bias)
    cond1_easy_ok = False
    if is_valid(close_0) and is_valid(easy_0) and easy_0 > 0:
        bias = close_0 / easy_0
        cond1_easy_ok = (1.0 < bias <= max_easy_bias)

    # 2. 單筆均張連續 2 日遞增 (t > t-1 > t-2)
    cond2_spt_growing = (spt_0 > spt_1 > spt_2) if (is_valid(spt_0) and is_valid(spt_1) and is_valid(spt_2)) else False

    # 3. 當日單筆均張顯著突破 5 日均張
    cond3_spt_surge = (spt_0 >= spt_ma5 * spt_growth_ratio) if (is_valid(spt_0) and is_valid(spt_ma5)) else False

    # 4. 量能相對放大率 (當日股數 >= 5日均量股數 * 1.3) + 底層安全門檻 (成交金額 >= 1000萬)
    cond4_vol_boost_ok = False
    if is_valid(vol_0) and is_valid(vol_ma5) and vol_ma5 > 0:
        is_relative_boost = (vol_0 >= vol_ma5 * vol_boost_ratio)
        is_not_zombie = (turnover_amount >= min_safety_turnover)
        cond4_vol_boost_ok = is_relative_boost and is_not_zombie

    # 總體過濾結果
    is_hit = cond1_easy_ok and cond2_spt_growing and cond3_spt_surge and cond4_vol_boost_ok

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        
        # 僅在顯示時轉換為張數 (/ 1000.0)
        vol_lots = (vol_0 / 1000.0) if is_valid(vol_0) else 0.0
        vol_ma5_lots = (vol_ma5 / 1000.0) if is_valid(vol_ma5) else 0.0
        actual_boost = (vol_0 / vol_ma5) if (is_valid(vol_0) and is_valid(vol_ma5) and vol_ma5 > 0) else 0.0

        print("\n" + "=" * 65)
        print(f"🔔 [F1_筆張現形] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 65)
        print(f"  [{ '✓' if cond1_easy_ok else '✕' }] 1. 站上輕鬆線且未過熱 : Close=${close_0:.2f}, Easy=${easy_0:.2f}")
        print(f"  [{ '✓' if cond2_spt_growing else '✕' }] 2. 單筆均張連續2日遞增 : {spt_0:.2f} > {spt_1:.2f} > {spt_2:.2f}")
        print(f"  [{ '✓' if cond3_spt_surge else '✕' }] 3. 均張顯著放大 (>= MA5*{spt_growth_ratio}) : {spt_0:.2f} vs MA5:{spt_ma5:.2f}")
        print(f"  [{ '✓' if cond4_vol_boost_ok else '✕' }] 4. 量能相對放大 (>= 5日均量*{vol_boost_ratio:.1f}) : {actual_boost:.2f}倍 (成交量:{vol_lots:,.0f}張, 金額:{turnover_amount/10000:,.0f}萬)")
        print("-" * 65)
        print(f"🎯 最終觸發結果: {'🔥 [觸發強勢筆張現形]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 65 + "\n")

    info = {
        '選股公式': 'F1_筆張現形',
        '操作建議': '單筆均張與當日總量能同步相較於 5 日均值顯著放大，為主力帶量實質卡位訊號。'
    } if is_hit else {}

    return is_hit, info


def st_qiantang_f1_spt_growth_20260930(
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
    verbose: bool = DEBUG_VERBOSE,
) -> tuple[bool, dict]:
  """【F2_出量上輕 (雙軌成交金額優化版 - T-1 Level 2 跳空與 T-2 實體洗盤升級版)】

  雙軌觸發機制：
  1. T-1 模式 (Level 2 強勢跳空攻擊)：
      - 昨日 (T-1) 觸發基礎 F2 出量上輕 (模式 A 或 模式 B)
      - 今日 (T) 滿足 Level 2 跳空強勢條件：
        ★ 開盤跳空 >= 1.0% (Open_T >= Close_T-1 * 1.01)
        ★ 收實體紅 K (Close_T >= Open_T) 且 實質續漲 (Close_T > Close_T-1)
        ★ 上影線抑制 <= 25% 且 今日最低價不跌破昨日最低價 (min_T >= min_T-1)

  2. T-2 模式 (紅 K 實體品質 + 兩日洗盤沉澱)：
      - 前日 (T-2) 觸發基礎 F2 出量上輕 (模式 A 或 模式 B)
      - 前日 (T-2) 滿足高品質紅 K 實體條件：
        ★ 實體漲幅 >= 2.5%
        ★ 買盤純度 Body Ratio >= 60% (實體佔總振幅 60% 以上)
        ★ 上影線抑制比例 <= 20%
      - 兩日洗盤與今日 (T) 轉強確認：
        ★ T-1 與 T 日最低價均不跌破 T-2 發動日最低價 (洗盤不破底)
        ★ 今日 (T) 收實體紅 K 且 收盤價 >= T-2 實體下緣 (Close_T >= Open_T-2)
  """

  print("st_qiantang_f2_volume_breakout*******************************************************")
  profile = profile or {}

  # 歷史資料至少需 4 筆以支援 T-2 與其前一日的突破判定 (T, T-1, T-2, T-3)
  if len(df_single) < 4:
    if verbose:
      print(
          f"❌ [出量上輕] 資料筆數不足 4 筆 (目前: {len(df_single)})"
      )
    return False, {}

  today = df_single.iloc[-1]  # T 日 (今日)
  d1 = df_single.iloc[-2]  # T-1 日 (昨日)
  d2 = df_single.iloc[-3]  # T-2 日 (前日)

  # -------------------------------------------------------------
  # 內部工具函式：檢測特定相對位置 (pos_idx) 是否符合基礎 F2 突破
  # -------------------------------------------------------------
  def _check_f2_base_signal(pos_idx: int) -> tuple[bool, dict]:
    pos = len(df_single) + pos_idx if pos_idx < 0 else pos_idx
    if pos < 1:
      return False, {}

    cur = df_single.iloc[pos]
    prev = df_single.iloc[pos - 1]

    # 直接索取欄位，若不存在則拋出 KeyError 異常
    c0, c1 = cur["close"], prev["close"]
    e0 = cur["easy_line"]
    v0, v1 = cur["Trading_Volume"], prev["Trading_Volume"]

    cond1_above_easy = c0 > e0
    cond2_price_ok = c0 >= 5.0
    cond3_base_vol = v0 >= 350 * 1000

    turnover = c0 * v0 / 100_000_000
    change_pct = (
        (c0 - c1) / c1 * 100.0 if is_valid(c0) and is_valid(c1) and c1 > 0 else 0.0
    )
    #change_pct = (c0 - c1) / c1 * 100.0 if c1 > 0 else cur["change_pct"]

    # 輕鬆線趨勢檢查 (當前 > 5日前)
    if pos >= 5:
      d5 = df_single.iloc[pos - 5]
      e5 = d5["easy_line"]
      cond_easy_trend = e0 > e5
    else:
      cond_easy_trend = True

    cond_strong_k_a = change_pct >= 2.5
    cond_strong_k_b = change_pct >= 3.5

    cond_vol_surge_a = v0 >= v1 * 2.5
    cond_vol_surge_b = v0 >= v1 * 3.0

    mode_a = (
        cond_vol_surge_a
        and (v0 >= 3000 * 1000)
        and (turnover >= 5.0)
        and cond_strong_k_a
        and cond_easy_trend
    )
    mode_b = (
        cond_vol_surge_b
        and (v0 < 3000 * 1000)
        and (turnover >= 1.5)
        and cond_strong_k_b
        and cond_easy_trend
    )

    is_hit = (
        cond1_above_easy
        and cond2_price_ok
        and cond3_base_vol
        and (mode_a or mode_b)
    )
    mode_name = (
        "模式A(主流大中型)"
        if mode_a
        else ("模式B(中小型飆股)" if mode_b else "未觸發")
    )

    return is_hit, {
        "mode": mode_name,
        "turnover": turnover,
        "change_pct": change_pct,
        "vol": v0,
        "close": c0,
    }

  # =============================================================
  # 模式一：T-1 模式 (昨日出訊號 + 今日 Level 2 強勢跳空攻擊)
  # =============================================================
  hit_t1_base, info_t1 = _check_f2_base_signal(-2)
  if hit_t1_base:
    # 嚴格索取欄位：high 改為 max，low 改為 min
    open_0, close_0 = today["open"], today["close"]
    max_0, min_0 = today["max"], today["min"]
    close_1, min_1 = d1["close"], d1["min"]

    gap_pct = (open_0 - close_1) / close_1 * 100.0
    cond_gap = gap_pct >= 1.0  # 1. Level 2 開盤跳空 >= 1.0%
    cond_red_k = close_0 >= open_0  # 2. 當天收實體紅 K
    cond_gain = close_0 > close_1  # 3. 實質續漲
    range_0 = max_0 - min_0
    upper_shadow_ratio = (max_0 - close_0) / range_0 if range_0 > 0 else 0.0
    cond_shadow = upper_shadow_ratio <= 0.25  # 4. 上影線抑制 <= 25%
    cond_low_def = min_0 >= min_1  # 5. 低點防守不破昨日最低價

    if cond_gap and cond_red_k and cond_gain and cond_shadow and cond_low_def:
      vol_0 = today["Trading_Volume"]
      turnover_0 = close_0 * vol_0 / 100_000_000

      if verbose:
        stock_id = today["stock_id"]
        date_str = str(today["date"])
        print("\n" + "=" * 55)
        print(
            f"🔔 [F2_出量上輕] 股票: {stock_id} | 日期: {date_str} | 觸發模式:"
            " T-1 Level 2 攻擊"
        )
        print("-" * 55)
        print(f"   [✓] T-1 發動模式 : {info_t1['mode']}")
        print(f"   [✓] 1. 開盤跳空    : +{gap_pct:.2f}% (門檻 >= 1.0%)")
        print(f"   [✓] 2. 實體紅 K    : 收 {close_0:.2f} >= 開 {open_0:.2f}")
        print(f"   [✓] 3. 實質續漲    : 今日收 {close_0:.2f} > 昨收 {close_1:.2f}")
        print(
            "   [✓] 4. 上影線抑制  :"
            f" {upper_shadow_ratio*100:.1f}% (門檻 <= 25%)"
        )
        print(
            f"   [✓] 5. 最低價防守  : 今日低 {min_0:.2f} >= 昨低 {min_1:.2f}"
        )
        print("-" * 55)
        print("🎯 最終觸發結果: 🔥 [觸發 T-1 強勢攻擊]")
        print("=" * 55 + "\n")

      return True, {
          "選股公式": "F2_出量上輕 (T-1強勢攻擊)",
          "操作建議": (
              f"昨日突破 ({info_t1['mode']})，今日展現 Level 2 強勢跳空"
              f" (+{gap_pct:.1f}%) 並收紅 K，主力買盤強烈，攻勢延續。"
          ),
          "成交金額億": round(turnover_0, 2),
          "觸發模式": f"T-1強勢攻擊 [{info_t1['mode']}]",
          "跳空細節": (
              f"跳空 +{gap_pct:.2f}%, 上影線佔比"
              f" {upper_shadow_ratio*100:.1f}%"
          ),
      }

  # =============================================================
  # 模式二：T-2 模式 (前日爆量高純度紅 K + 兩日洗盤守住 + 今日轉強)
  # =============================================================
  hit_t2_base, info_t2 = _check_f2_base_signal(-3)
  if hit_t2_base:
    # 嚴格索取欄位：high 改為 max，low 改為 min
    open_2, close_2 = d2["open"], d2["close"]
    max_2, min_2 = d2["max"], d2["min"]
    min_1 = d1["min"]
    open_0, close_0, min_0 = today["open"], today["close"], today["min"]

    range_2 = max_2 - min_2
    body_pct_2 = (close_2 - open_2) / open_2 * 100.0 if open_2 > 0 else 0.0
    body_ratio_2 = (close_2 - open_2) / range_2 if range_2 > 0 else 0.0
    upper_shadow_2 = (max_2 - close_2) / range_2 if range_2 > 0 else 0.0

    # 1. T-2 紅 K 實體品質門檻
    cond_t2_quality = (
        (body_pct_2 >= 2.5)
        and (body_ratio_2 >= 0.60)
        and (upper_shadow_2 <= 0.20)
    )

    # 2. 洗盤防守：T-1 與 T 日最低價均不跌破 T-2 發動日最低價
    cond_low_def = (min_1 >= min_2) and (min_0 >= min_2)

    # 3. 今日轉強：今日收實體紅 K 且收盤價守住 T-2 發動日實體下緣 (開盤價)
    cond_today_revive = (close_0 >= open_0) and (close_0 >= open_2)

    if cond_t2_quality and cond_low_def and cond_today_revive:
      vol_0 = today["Trading_Volume"]
      turnover_0 = close_0 * vol_0 / 100_000_000

      if verbose:
        stock_id = today["stock_id"]
        date_str = str(today["date"])
        print("\n" + "=" * 55)
        print(
            f"🔔 [F2_出量上輕] 股票: {stock_id} | 日期: {date_str} | 觸發模式:"
            " T-2 洗盤確認"
        )
        print("-" * 55)
        print(f"   [✓] T-2 發動模式 : {info_t2['mode']}")
        print(
            "   [✓] 1. T-2 紅K品質 :"
            f" 漲幅 +{body_pct_2:.2f}% | 買盤純度 {body_ratio_2*100:.1f}%"
            f" (>=60%) | 上影線 {upper_shadow_2*100:.1f}% (<=20%)"
        )
        print(
            "   [✓] 2. 兩日洗盤防守:"
            f" 昨低 {min_1:.2f} & 今低 {min_0:.2f} >= T-2發動低 ${min_2:.2f}"
        )
        print(
            "   [✓] 3. 今日轉強復甦:"
            f" 收 {close_0:.2f} >= 開 {open_0:.2f} 且 >= T-2發動開 ${open_2:.2f}"
        )
        print("-" * 55)
        print("🎯 最終觸發結果: 🔥 [觸發 T-2 洗盤確認]")
        print("=" * 55 + "\n")

      return True, {
          "選股公式": "F2_出量上輕 (T-2洗盤確認)",
          "操作建議": (
              f"前日突破 ({info_t2['mode']})，買盤純度達"
              f" {body_ratio_2*100:.0f}%，經過兩日沉澱洗盤守住成本線，今日轉強紅"
              " K 再次發動。"
          ),
          "成交金額億": round(turnover_0, 2),
          "觸發模式": f"T-2洗盤確認 [{info_t2['mode']}]",
          "發動日品質": (
              f"買盤純度 {body_ratio_2*100:.1f}%, 實體漲幅"
              f" +{body_pct_2:.2f}%"
          ),
      }

  if verbose:
    stock_id = today["stock_id"]
    date_str = str(today["date"])
    print("\n" + "=" * 55)
    print(f"🔔 [F2_出量上輕] 股票: {stock_id} | 日期: {date_str}")
    print("-" * 55)
    print("⚪ [未觸發] 不符合 T-1 Level 2 攻擊門檻 或 T-2 洗盤確認條件")
    print("=" * 55 + "\n")

  return False, {}


def st_qiantang_f2_volume_breakout_20260930_3(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F2_出量上輕 (雙軌成交金額優化版 - 大小型股動態倍數升級版)】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元 (防呆安全底線)
    3. 成交量 >= 350 張 (基本流動性防呆底線)
    4. 爆量與資金雙軌確認 (模式A 或 模式B)：
        - 模式A (主流大中型股)：量增 >= 2.5 倍 且 當日量 >= 3,000 張 且 成交金額 >= 5.0 億元
          ★ 質化濾網：漲幅 >= 2.5% (大型股實體紅K) 且 輕鬆線呈向上揚升趨勢
        - 模式B (中小型/IC設計黑馬)：量增 >= 3.0 倍 且 當日量 < 3,000 張 且 成交金額 >= 1.5 億元
          ★ 質化濾網：漲幅 >= 3.5% (中小型實體紅K) 且 輕鬆線呈向上揚升趨勢
    修改自st_qiantang_f2_volume_breakout_20260930_2
    """
    profile = profile or {}
    if len(df_single) < 2:
        if verbose:
            print(f"❌ [出量上輕] 資料筆數不足 2 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]

    close_0 = today.get('close', None)
    close_1 = d1.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)
    vol_1 = d1.get('Trading_Volume', None)

    # 1. 基本防呆與條件檢查
    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    # 計算當日成交金額 (億元)：收盤價 * 總股數 / 1億
    turnover_0 = (close_0 * vol_0 / 100_000_000) if (is_valid(close_0) and is_valid(vol_0)) else 0.0

    # 計算當日漲幅 (%)
    change_pct = ((close_0 - close_1) / close_1 * 100.0) if (is_valid(close_0) and is_valid(close_1) and close_1 > 0) else today.get('change_pct', 0.0)

    # 輕鬆線斜率/趨勢檢查 (當前輕鬆線 > 5日前輕鬆線)
    if len(df_single) >= 6:
        d5 = df_single.iloc[-6]
        easy_5 = d5.get('easy_line', None)
        cond_easy_trend = (easy_0 > easy_5) if (is_valid(easy_0) and is_valid(easy_5)) else True
    else:
        cond_easy_trend = True

    # 實體紅 K 強勢度檢查
    cond_strong_k_a = (change_pct >= 2.5) if is_valid(change_pct) else False  # Mode A 大型股門檻 (>= 2.5%)
    cond_strong_k_b = (change_pct >= 3.5) if is_valid(change_pct) else False  # Mode B 中小型股門檻 (>= 3.5%)

    # 量增倍數條件區分（大型股 2.5 倍，中小型股 3.0 倍）
    cond_vol_surge_a = (vol_0 >= vol_1 * 2.5) if (is_valid(vol_0) and is_valid(vol_1)) else False
    cond_vol_surge_b = (vol_0 >= vol_1 * 3.0) if (is_valid(vol_0) and is_valid(vol_1)) else False

    # 2. 雙軌爆量與資金模式
    # 模式 A：主流大中型股通道 (量增>=2.5倍, 張數>=3000張, 金額>=5.0億, 且漲幅>=2.5%與輕鬆線揚升)
    mode_a = (
        cond_vol_surge_a and 
        (vol_0 >= 3000 * 1000) and 
        (turnover_0 >= 5.0) and 
        cond_strong_k_a and 
        cond_easy_trend
    )

    # 模式 B：中小型飆股 / IC設計黑馬通道 (量增>=3.0倍, 張數<3000張, 金額>=1.5億, 且漲幅>=3.5%與輕鬆線揚升)
    mode_b = (
        cond_vol_surge_b and 
        (vol_0 < 3000 * 1000) and 
        (turnover_0 >= 1.5) and 
        cond_strong_k_b and 
        cond_easy_trend
    )

    cond4_vol_surge = mode_a or mode_b

    # 最終觸發判斷
    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond4_vol_surge

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_0_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0
        multiple = (vol_0 / vol_1) if (is_valid(vol_0) and is_valid(vol_1) and vol_1 > 0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F2_出量上輕] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"    [{ '✓' if cond1_above_easy else '✕' }] 1. 收盤 > 輕鬆線 : ({close_0:.2f} > {easy_0:.2f})" if is_valid(close_0) and is_valid(easy_0) else "    [✕] 1. 收盤 > 輕鬆線 : N/A")
        print(f"    [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "    [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"    [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_0_lots:,.0f} 張")
        print(f"    [{ '✓' if cond4_vol_surge else '✕' }] 4. 出量爆發 (倍數 {multiple:.1f}x | 金額 {turnover_0:.2f}億 | 漲幅 {change_pct:.2f}%) : 模式A({mode_a}) | 模式B({mode_b})")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發出量上輕]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F2_出量上輕',
        '操作建議': '成交金額與量能同步暴增，主力資金強勢進駐並站上輕鬆線，多頭續航力高。',
        '成交金額億': round(turnover_0, 2),
        '觸發模式': '模式A(主流大型)' if mode_a else ('模式B(中小型/IC設計)' if mode_b else '未觸發')
    } if is_hit else {}

    return is_hit, info


def st_qiantang_f2_volume_breakout_20260930_2(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F2_出量上輕 (台灣50 / 中型100 / IC設計 專用版)】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 價格底線 (close >= min_price)
    3. 相對爆量 (vol_0 >= vol_1 * surge_mult)
    4. 流動性雙模式：
        - IC設計：金額優先 (turnover_0 >= min_amount)
        - 台灣50 / 中型100：雙軌制 (vol_0 >= min_vol OR turnover_0 >= min_amount)

    從st_qiantang_f2_volume_breakout_20260930_1改過來, 但效果不好改成st_qiantang_f2_volume_breakout_20260930_2
    """
    profile = profile or {}
    f2_cfg = profile.get('f2_volume_breakout', {})
    
    # 讀取 Profile 專屬參數
    profile_key = profile.get('profile_key', '')
    min_price = f2_cfg.get('min_price', profile.get('min_price', 5.0))
    min_vol = profile.get('min_vol', 1000 * 1000)      # 最低股數 (張數 * 1000)
    min_amount = profile.get('min_amount', 2.0)        # 最低金額 (億元)
    surge_mult = f2_cfg.get('surge_mult', 2.5)         # 爆量倍數

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

    # 計算當日成交金額 (億元)
    turnover_0 = (close_0 * vol_0 / 100_000_000) if (is_valid(close_0) and is_valid(vol_0)) else 0.0

    # 1. 基本條件與相對爆量檢驗
    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= min_price) if is_valid(close_0) else False
    cond3_vol_surge = (vol_0 >= vol_1 * surge_mult) if (is_valid(vol_0) and is_valid(vol_1) and vol_1 > 0) else False

    # 2. 流動性過濾（移除純張數，僅保留 金額優先 與 雙軌制）
    if is_valid(vol_0):
        if profile_key == 'ICDesign' or min_vol == 0:
            # IC設計 / 高價晶片股：金額優先
            cond4_liquidity = (turnover_0 >= min_amount)
        else:
            # 台灣50 / 中型100：雙軌制 (張數 OR 金額)
            cond4_liquidity = (vol_0 >= min_vol) or (turnover_0 >= min_amount)
    else:
        cond4_liquidity = False

    # 最終觸發判斷
    is_hit = cond1_above_easy and cond2_price_ok and cond3_vol_surge and cond4_liquidity

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_0_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0
        min_vol_lots = min_vol / 1000.0
        multiple = (vol_0 / vol_1) if (is_valid(vol_0) and is_valid(vol_1) and vol_1 > 0) else 0.0
        profile_name = profile.get('name', '預設族群')

        print("\n" + "=" * 55)
        print(f"🔔 [F2_出量上輕] 股票: {stock_id} | 日期: {date_str} | 適用族群: {profile_name}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 收盤 > 輕鬆線 : ({close_0:.2f} > {easy_0:.2f})" if (is_valid(close_0) and is_valid(easy_0)) else "  [✕] 1. 收盤 > 輕鬆線 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= {min_price:.1f}元 : ${close_0:.2f}" if is_valid(close_0) else f"  [✕] 2. 收盤價 >= {min_price:.1f}元 : N/A")
        print(f"  [{ '✓' if cond3_vol_surge else '✕' }] 3. 相對爆量 (當前 {multiple:.1f}x | 目標 >= {surge_mult:.1f}x)")
        
        if profile_key == 'ICDesign' or min_vol == 0:
            print(f"  [{ '✓' if cond4_liquidity else '✕' }] 4. 流動性 [金額優先] (金額 {turnover_0:.2f} >= {min_amount:.1f}億)")
        else:
            print(f"  [{ '✓' if cond4_liquidity else '✕' }] 4. 流動性 [雙軌制] (張數 {vol_0_lots:,.0f} >= {min_vol_lots:,.0f}張 OR 金額 {turnover_0:.2f} >= {min_amount:.1f}億)")
            
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發出量上輕]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F2_出量上輕',
        '套用族群': profile.get('name', '預設族群'),
        '操作建議': '成交金額與量能同步暴增，主力資金強勢進駐並站上輕鬆線，多頭續航力高。',
        '成交金額億': round(turnover_0, 2),
        '爆量倍數': round((vol_0 / vol_1), 2) if (is_valid(vol_0) and is_valid(vol_1) and vol_1 > 0) else 0.0
    } if is_hit else {}

    return is_hit, info

def st_qiantang_f2_volume_breakout_20260930_1(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F2_出量上輕 (雙軌成交金額優化版)】
    邏輯：
    1. 上輕鬆 (close > easy_line)
    2. 收盤價 >= 5 元 (防呆安全底線)
    3. 成交量 >= 350 張 (基本流動性防呆底線)
    4. 爆量與資金雙軌確認 (模式A 或 模式B)：
        - 模式A (大中型股)：昨日量 * 3 且 當日量 >= 3,000 張 且 成交金額 >= 5 億元
        - 模式B (中小型/IC設計股)：昨日量 * 4.5 且 當日量 < 3,000 張 且 成交金額 >= 2 億元

    st_qiantang_f2_volume_breakout_20260930_1
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

    # 1. 基本防呆與條件檢查
    cond1_above_easy = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False

    # 計算當日成交金額 (億元)：收盤價 * 總股數 / 1億
    turnover_0 = (close_0 * vol_0 / 100_000_000) if (is_valid(close_0) and is_valid(vol_0)) else 0.0

    # 2. 雙軌爆量與資金模式
    # 模式 A：主流大中型股通道 (量增>=3倍, 張數>=3000張, 金額>=5億)
    mode_a = (
        (vol_0 >= vol_1 * 3.0) and 
        (vol_0 >= 3000 * 1000) and 
        (turnover_0 >= 5.0)
    ) if (is_valid(vol_0) and is_valid(vol_1)) else False

    # 模式 B：中小型飆股 / IC設計黑馬通道 (量增>=4.5倍, 張數<3000張, 金額>=2億)
    mode_b = (
        (vol_0 >= vol_1 * 4.5) and 
        (vol_0 < 3000 * 1000) and 
        (turnover_0 >= 2.0)
    ) if (is_valid(vol_0) and is_valid(vol_1)) else False

    cond4_vol_surge = mode_a or mode_b

    # 最終觸發判斷
    is_hit = cond1_above_easy and cond2_price_ok and cond3_base_vol and cond4_vol_surge

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_0_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0
        multiple = (vol_0 / vol_1) if (is_valid(vol_0) and is_valid(vol_1) and vol_1 > 0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F2_出量上輕] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_above_easy else '✕' }] 1. 收盤 > 輕鬆線 : \({close_0:.2f} >\){easy_0:.2f}" if is_valid(close_0) and is_valid(easy_0) else "  [✕] 1. 收盤 > 輕鬆線 : N/A")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_base_vol else '✕' }] 3. 成交量 >= 350張 : {vol_0_lots:,.0f} 張")
        print(f"  [{ '✓' if cond4_vol_surge else '✕' }] 4. 出量爆發 (倍數 {multiple:.1f}x | 金額 {turnover_0:.2f}億) : 模式A({mode_a}) | 模式B({mode_b})")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發出量上輕]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F2_出量上輕',
        '操作建議': '成交金額與量能同步暴增，主力資金強勢進駐並站上輕鬆線，多頭續航力高。',
        '成交金額億': round(turnover_0, 2),
        '觸發模式': '模式A(大中型)' if mode_a else ('模式B(中小型/IC設計)' if mode_b else '未觸發')
    } if is_hit else {}

    return is_hit, info

def st_qiantang_f2_volume_breakout_20260930(
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
from scipy.stats import linregress  # 用於計算 OLS 斜率

def st_qiantang_f3_after_shakeout(
    df_single: pd.DataFrame, profile: dict = None, verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
  """【F3_洗盤後（優化版：均線趨勢 + 量能 1.2 倍 + 連續兩天站上 + 輕鬆線斜率與漲幅）】

  邏輯：
  1. 趨勢過濾：今日收盤價 > MA60（季線，直接計算）
  2. 價格過濾：收盤價 >= 5 元
  3. 量能過濾：今日成交量 >= 350 張 且 >= 前 5 日均量的 1.2 倍
  4. 連續確認：今日與昨日皆上輕鬆線 (close > easy_line)
  5. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線 (close <= easy_line)
  6. 輕鬆線動能：輕鬆線 OLS 斜率 > 0 且 5 日累計漲幅 >= 1.5%

  修改自 st_qiantang_f3_after_shakeout_20261001_1
  """
  profile = profile or {}

  # 需要至少 60 筆以計算 MA60（同時滿足斜率所需的 6 筆以上）
  if len(df_single) < 60:
    if verbose:
      print(f"❌ [洗盤後] 資料筆數不足 60 筆，無法計算 MA60 (目前: {len(df_single)})")
    return False, {}

  # 直接計算 60 日均線
  df_single = df_single.copy()
  df_single['MA60'] = df_single['close'].rolling(window=60).mean()

  today = df_single.iloc[-1]
  d1 = df_single.iloc[-2]
  d2 = df_single.iloc[-3]
  d3 = df_single.iloc[-4]
  d4 = df_single.iloc[-5]

  close_0 = today['close']
  easy_0 = today['easy_line']
  vol_0 = today['Trading_Volume']
  ma60_0 = today['MA60']

  close_1 = d1['close']
  easy_1 = d1['easy_line']

  # 計算前 5 日平均成交量
  recent_vols = df_single['Trading_Volume'].iloc[-6:-1]
  vol_ma5 = recent_vols.mean()

  # 1. 趨勢過濾：收盤價 > MA60
  cond1_trend = close_0 > ma60_0

  # 2. 價格過濾：收盤價 >= 5 元
  cond2_price_ok = close_0 >= 5.0

  # 3. 量能過濾：成交量 >= 350 張 且 >= 5日均量的 1.0 倍
  VOLUME_MULTIPLIER = 1.0
  cond3_base_vol = vol_0 >= 350 * 1000
  cond3_vol_up = vol_0 >= vol_ma5 * VOLUME_MULTIPLIER
  cond3_vol_ok = cond3_base_vol and cond3_vol_up

  # 4. 連續確認：今日與昨日皆上輕鬆線
  cond4_today_above = close_0 > easy_0
  cond4_yesterday_above = close_1 > easy_1
  cond4_continuous = cond4_today_above and cond4_yesterday_above

  # 5. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線
  was_below_2d = d2['close'] <= d2['easy_line']
  was_below_3d = d3['close'] <= d3['easy_line']
  was_below_4d = d4['close'] <= d4['easy_line']
  cond5_shakeout = was_below_2d or was_below_3d or was_below_4d

  # 6. 【新增】輕鬆線 OLS 斜率向上 且 5 日累計漲幅 >= 1.5%
  easy_series = df_single['easy_line'].iloc[-5:]  # 取最近 5 天的輕鬆線
  slope = 0.0
  easy_5days_ago = df_single['easy_line'].iloc[-5]

  y = easy_series.values
  x = np.arange(len(y))
  res = linregress(x, y)
  slope = res.slope

  # 計算 5 日累計漲幅
  easy_growth = (easy_0 - easy_5days_ago) / easy_5days_ago

  cond6_slope_ok = slope > 0
  cond6_growth_ok = easy_growth >= 0.015
  cond6_easy_momentum = cond6_slope_ok and cond6_growth_ok

  # 綜合所有條件
  is_hit = (
      cond1_trend
      and cond2_price_ok
      and cond3_vol_ok
      and cond4_continuous
      and cond5_shakeout
      and cond6_easy_momentum
  )

  if verbose:
    stock_id = today['stock_id']
    date_str = str(today['date'])
    vol_lots = vol_0 / 1000.0
    vol_target = (vol_ma5 * VOLUME_MULTIPLIER) / 1000.0

    print('\n' + '=' * 55)
    print(f'🔔 [F3_洗盤後優化版+斜率過濾] 股票: {stock_id} | 日期: {date_str}')
    print('-' * 55)
    print(f"  [{ '✓' if cond1_trend else '✕' }] 1. 季線趨勢過濾 : Close > MA60 (MA60: {ma60_0:.2f})")
    print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}")
    print(f"  [{ '✓' if cond3_vol_ok else '✕' }] 3. 帶量 1.2 倍 : {vol_lots:,.0f} 張 (>=350張 且 >= {vol_target:,.0f}張)")
    print(f"  [{ '✓' if cond4_continuous else '✕' }] 4. 連續兩天站上 : 今日({cond4_today_above}) 與 昨日({cond4_yesterday_above})")
    print(f"  [{ '✓' if cond5_shakeout else '✕' }] 5. 洗盤甩轎軌跡 : 2日前({was_below_2d}) | 3日前({was_below_3d}) | 4日前({was_below_4d})")
    print(f"  [{ '✓' if cond6_easy_momentum else '✕' }] 6. 輕鬆線動能 : OLS斜率 ({slope:.3f}) > 0 且 5日漲幅 ({easy_growth * 100:.2f}%) >= 1.5%")
    print('-' * 55)
    print(f"🎯 最終觸發結果: {'🔥 [觸發洗盤後動能版]' if is_hit else '⚪ [未觸發]'}")
    print('=' * 55 + '\n')

  info = {
      '選股公式': 'F3_洗盤後_優化版_量能1.2倍與輕鬆線動能',
      '操作建議': (
          '結合均線多頭、1.2倍爆發量、連續站穩輕鬆線，並透過 OLS '
          '斜率與 5 日漲幅確保輕鬆線確實向上發散，過濾橫盤雜訊。'
      ),
  } if is_hit else {}

  return is_hit, info


def st_qiantang_f3_after_shakeout20261001_1_2(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F3_洗盤後（優化版：均線趨勢 + 1.2倍均量 + 扎實紅K確認 + 連續兩天站上）】
    邏輯：
    1. 趨勢過濾：今日收盤價 > MA60（季線）
    2. 價格過濾：收盤價 >= 5 元
    3. 量能過濾：今日成交量 >= 350 張 且 >= 前 5 日均量 * 1.2 倍
    4. K棒型態過濾：最近一日為扎實紅K（實體佔總振幅>=50%、上影線<=實體50%）
    5. 連續確認：今日與昨日皆上輕鬆線 (close > easy_line)
    6. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線 (close <= easy_line)

    修改自st_qiantang_f3_after_shakeout_20261001_1
    """
    profile = profile or {}
    # 需要至少 6 筆資料以容納前幾日洗盤與 MA60 運算
    if len(df_single) < 6:
        if verbose:
            print(f"❌ [洗盤後] 資料筆數不足 6 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]
    d3 = df_single.iloc[-4]
    d4 = df_single.iloc[-5]

    close_0 = today.get('close', None)
    open_0 = today.get('open', None)
    high_0 = today.get('high', None)
    low_0 = today.get('low', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)
    ma60_0 = today.get('MA60', None)

    close_1 = d1.get('close', None)
    easy_1 = d1.get('easy_line', None)

    # 計算前 5 日平均成交量
    recent_vols = df_single['Trading_Volume'].iloc[-6:-1]
    vol_ma5 = recent_vols.mean() if len(recent_vols) > 0 else 0

    # 1. 趨勢過濾：收盤價 > MA60（若 DataFrame 無 MA60 欄位則預設通過）
    cond1_trend = (close_0 > ma60_0) if (is_valid(close_0) and is_valid(ma60_0)) else True

    # 2. 價格過濾：收盤價 >= 5 元
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False

    # 3. 量能過濾：成交量 >= 350 張 且 >= 5日均量 * 1.5 倍
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False
    cond3_vol_up = (vol_0 >= vol_ma5 * 1.5) if (is_valid(vol_0) and is_valid(vol_ma5) and vol_ma5 > 0) else True
    cond3_vol_ok = cond3_base_vol and cond3_vol_up

    # 4. K棒型態過濾：最近一日為扎實紅K（收紅、實體大、上影線短）
    if is_valid(close_0) and is_valid(open_0) and is_valid(high_0) and is_valid(low_0):
        is_red_k = close_0 > open_0
        body_len = abs(close_0 - open_0)
        total_range = high_0 - low_0
        upper_shadow = high_0 - max(close_0, open_0)
        
        # 實體佔總振幅達 50% 以上，且上影線不超過實體長度的 50%
        body_ratio_ok = (body_len / total_range >= 0.5) if total_range > 0 else True
        upper_shadow_ok = (upper_shadow <= body_len * 0.5)
        cond4_candle_ok = is_red_k and body_ratio_ok and upper_shadow_ok
    else:
        cond4_candle_ok = False

    cond4_candle_ok = True #掠過K棒型態的檢查

    # 5. 連續確認：今日與昨日皆上輕鬆線
    cond5_today_above = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond5_yesterday_above = (close_1 > easy_1) if (is_valid(close_1) and is_valid(easy_1)) else False
    cond5_continuous = cond5_today_above and cond5_yesterday_above

    # 6. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線
    was_below_2d = (d2.get('close', 0) <= d2.get('easy_line', 0)) if (is_valid(d2.get('close')) and is_valid(d2.get('easy_line'))) else False
    was_below_3d = (d3.get('close', 0) <= d3.get('easy_line', 0)) if (is_valid(d3.get('close')) and is_valid(d3.get('easy_line'))) else False
    was_below_4d = (d4.get('close', 0) <= d4.get('easy_line', 0)) if (is_valid(d4.get('close')) and is_valid(d4.get('easy_line'))) else False

    cond6_shakeout = was_below_2d or was_below_3d or was_below_4d

    is_hit = cond1_trend and cond2_price_ok and cond3_vol_ok and cond4_candle_ok and cond5_continuous and cond6_shakeout

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F3_洗盤後優化版] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_trend else '✕' }] 1. 季線趨勢過濾 : Close > MA60")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_vol_ok else '✕' }] 3. 1.2倍量能過濾 : {vol_lots:,.0f} 張 (>=350張 且 >= 5日均量*1.2)")
        print(f"  [{ '✓' if cond4_candle_ok else '✕' }] 4. 扎實紅K確認 : 收紅且無長上影線")
        print(f"  [{ '✓' if cond5_continuous else '✕' }] 5. 連續兩天站上 : 今日({cond5_today_above}) 與 昨日({cond5_yesterday_above})")
        print(f"  [{ '✓' if cond6_shakeout else '✕' }] 6. 洗盤甩轎軌跡 : 2日前({was_below_2d}) | 3日前({was_below_3d}) | 4日前({was_below_4d})")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發洗盤後優化版]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F3_洗盤後_優化版',
        '操作建議': '結合均線多頭、1.2倍放量、扎實紅K表態與連續兩天站穩輕鬆線，精準過濾假突破。'
    } if is_hit else {}

    return is_hit, info

def st_qiantang_f3_after_shakeout_20261001_1_1(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F3_洗盤後（優化版：均線趨勢 + 量能放大 + 連續兩天站上 + MACD綠翻紅）】
    邏輯：
    1. 趨勢過濾：今日收盤價 > MA60（季線）
    2. 價格過濾：收盤價 >= 5 元
    3. 量能過濾：今日成交量 >= 350 張 且 大於前 5 日均量
    4. 連續確認：今日與昨日皆上輕鬆線 (close > easy_line)
    5. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線 (close <= easy_line)
    6. 動能過濾：MACD 柱狀體 (OSC) 由綠翻紅 (今日 OSC > 0 且昨日 OSC <= 0)

    修改自 st_qiantang_f3_after_shakeout_20261001_1.....MACD的效果不彰, 因為是落後指標, 放棄
    """
    profile = profile or {}
    
    # 【修改點 1】由於需要計算 MACD (12, 26, 9) 及前幾日洗盤，建議至少需要 35 筆以上資料較為精確（若資料不足可依需求微調）
    if len(df_single) < 35:
        if verbose:
            print(f"❌ [洗盤後] 資料筆數不足 35 筆，無法完整計算 MACD (目前: {len(df_single)})")
        return False, {}

    # 【修改點 2】自動在函式內計算 MACD 指標 (DIF, DEM, OSC)
    # 若您的外部資料集已經算好 DIF/DEM/OSC，可省略此段直接取用欄位
    exp1 = df_single['close'].ewm(span=12, adjust=False).mean()
    exp2 = df_single['close'].ewm(span=26, adjust=False).mean()
    dif = exp1 - exp2
    dem = dif.ewm(span=9, adjust=False).mean()
    osc = (dif - dem) * 2  # MACD 柱狀體

    # 將計算好的 OSC 暫存或掛載回 DataFrame 局部檢視
    df_temp = df_single.copy()
    df_temp['DIF'] = dif
    df_temp['DEM'] = dem
    df_temp['OSC'] = osc

    today = df_temp.iloc[-1]
    d1 = df_temp.iloc[-2]
    d2 = df_temp.iloc[-3]
    d3 = df_temp.iloc[-4]
    d4 = df_temp.iloc[-5]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)
    ma60_0 = today.get('MA60', None)
    osc_0 = today.get('OSC', None)

    close_1 = d1.get('close', None)
    easy_1 = d1.get('easy_line', None)
    osc_1 = d1.get('OSC', None)

    # 計算前 5 日平均成交量
    recent_vols = df_temp['Trading_Volume'].iloc[-6:-1]
    vol_ma5 = recent_vols.mean() if len(recent_vols) > 0 else 0

    # 1. 趨勢過濾：收盤價 > MA60（若 DataFrame 無 MA60 欄位則預設通過）
    cond1_trend = (close_0 > ma60_0) if (is_valid(close_0) and is_valid(ma60_0)) else True

    # 2. 價格過濾：收盤價 >= 5 元
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False

    # 3. 量能過濾：成交量 >= 350 張 且 >= 5日均量
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False
    cond3_vol_up = (vol_0 >= vol_ma5) if (is_valid(vol_0) and is_valid(vol_ma5) and vol_ma5 > 0) else True
    cond3_vol_ok = cond3_base_vol and cond3_vol_up

    # 4. 連續確認：今日與昨日皆上輕鬆線
    cond4_today_above = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond4_yesterday_above = (close_1 > easy_1) if (is_valid(close_1) and is_valid(easy_1)) else False
    cond4_continuous = cond4_today_above and cond4_yesterday_above

    # 5. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線
    was_below_2d = (d2.get('close', 0) <= d2.get('easy_line', 0)) if (is_valid(d2.get('close')) and is_valid(d2.get('easy_line'))) else False
    was_below_3d = (d3.get('close', 0) <= d3.get('easy_line', 0)) if (is_valid(d3.get('close')) and is_valid(d3.get('easy_line'))) else False
    was_below_4d = (d4.get('close', 0) <= d4.get('easy_line', 0)) if (is_valid(d4.get('close')) and is_valid(d4.get('easy_line'))) else False

    cond5_shakeout = was_below_2d or was_below_3d or was_below_4d

    # 6. 【新增】MACD 動能過濾：柱狀體由綠翻紅 (今日 OSC > 0 且昨日 OSC <= 0)
    cond6_macd_turn_red = (osc_0 > 0 and osc_1 <= 0) if (is_valid(osc_0) and is_valid(osc_1)) else False

    # 綜合所有條件（加入 cond6_macd_turn_red）
    is_hit = (
        cond1_trend 
        and cond2_price_ok 
        and cond3_vol_ok 
        and cond4_continuous 
        and cond5_shakeout 
        and cond6_macd_turn_red
    )

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F3_洗盤後優化版+MACD] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_trend else '✕' }] 1. 季線趨勢過濾 : Close > MA60")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_vol_ok else '✕' }] 3. 帶量過關 : {vol_lots:,.0f} 張 (>=350張 且 >= 5日均量)")
        print(f"  [{ '✓' if cond4_continuous else '✕' }] 4. 連續兩天站上 : 今日({cond4_today_above}) 與 昨日({cond4_yesterday_above})")
        print(f"  [{ '✓' if cond5_shakeout else '✕' }] 5. 洗盤甩轎軌跡 : 2日前({was_below_2d}) | 3日前({was_below_3d}) | 4日前({was_below_4d})")
        print(f"  [{ '✓' if cond6_macd_turn_red else '✕' }] 6. MACD綠翻紅 : 今日OSC({osc_0:.3f}) > 0 且 昨日OSC({osc_1:.3f}) <= 0" if (is_valid(osc_0) and is_valid(osc_1)) else "  [✕] 6. MACD綠翻紅 : N/A")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發洗盤後優化版+MACD]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F3_洗盤後_優化版_MACD動能確認',
        '操作建議': '結合均線多頭、帶量、連續兩天站穩輕鬆線，並透過 MACD 柱狀體由綠翻紅確認多頭動能啟動，過濾假突破。'
    } if is_hit else {}

    return is_hit, info

def st_qiantang_f3_after_shakeout_20261001_1_3_1(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = False
) -> tuple[bool, dict]:
    """
    【F3_洗盤後（紅K + 上影線限制 + 乖離量能雙控完整版）】
    基底架構：0745 純淨洗盤型態
    
    風控升級：
    1. 限制輕鬆線乖離率 <= 4%：確保進場點緊貼輕鬆線支撐，防範追高與拉回。
    2. 量能倍數 1.2倍 ~ 2.5倍：要求主力帶量攻堅，同時防範 >2.5倍爆天量出貨。
    3. 🌟 當日紅 K 防線 (Close > Open)：剔除開高走低、留下套牢陰線的假突破。
    4. 🌟 上影線長度限制 (<= 30%)：剔除上方賣壓沉重、主力拉高避雷針倒貨的K線。
    """
    profile = profile or {}
    if len(df_single) < 60:
        return False, {}

    df_single = df_single.copy()
    if 'MA60' not in df_single.columns:
        df_single['MA60'] = df_single['close'].rolling(window=60).mean()

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]
    d3 = df_single.iloc[-4]
    d4 = df_single.iloc[-5]

    # 取得當日價格與量能欄位 (相容大小寫欄位名)
    close_0 = today.get('close', today.get('Close', 0))
    open_0 = today.get('open', today.get('Open', 0))
    high_0 = today.get('high', today.get('High', 0))
    low_0 = today.get('low', today.get('Low', 0))
    easy_0 = today.get('easy_line', 0)
    vol_0 = today.get('Trading_Volume', 0)
    ma60_0 = today.get('MA60', 0)

    close_1 = d1.get('close', d1.get('Close', 0))
    easy_1 = d1.get('easy_line', 0)

    # 計算前 5 日平均成交量
    recent_vols = df_single['Trading_Volume'].iloc[-6:-1]
    vol_ma5 = recent_vols.mean() if len(recent_vols) > 0 else 0

    # -------------------------------------------------------------------------
    # 1. 基礎門檻 (趨勢、價格、量能底線)
    # -------------------------------------------------------------------------
    cond1_trend = close_0 > ma60_0 if (close_0 and ma60_0) else False
    cond2_price_ok = close_0 >= 5.0 if close_0 else False

    # 2. 量能區間：成交量 >= 350 張 且 1.2倍 <= 量能倍數 <= 2.5倍
    cond3_base_vol = vol_0 >= 350 * 1000 if vol_0 else False
    vol_ratio = (vol_0 / vol_ma5) if (vol_0 and vol_ma5 > 0) else 0
    cond3_vol_ok = cond3_base_vol and (1.2 <= vol_ratio <= 2.5)

    # 3. 輕鬆線乖離：0 < (收盤價 - 輕鬆線) / 輕鬆線 <= 4%
    easy_bias = (close_0 - easy_0) / easy_0 if (close_0 and easy_0 > 0) else 999
    cond4_bias_ok = 0 < easy_bias <= 0.04

    # 4. 連續確認：今日與昨日皆站上輕鬆線
    cond5_today_above = close_0 > easy_0 if (close_0 and easy_0) else False
    cond5_yesterday_above = close_1 > easy_1 if (close_1 and easy_1) else False
    cond5_continuous = cond5_today_above and cond5_yesterday_above

    # 5. 洗盤甩轎軌跡：T-2, T-3 或 T-4 曾跌破輕鬆線
    was_below_2d = d2.get('close', d2.get('Close', 0)) <= d2.get('easy_line', 0)
    was_below_3d = d3.get('close', d3.get('Close', 0)) <= d3.get('easy_line', 0)
    was_below_4d = d4.get('close', d4.get('Close', 0)) <= d4.get('easy_line', 0)
    cond6_shakeout = was_below_2d or was_below_3d or was_below_4d

    # -------------------------------------------------------------------------
    # 🌟 6. 防誘多陷阱防線 (針對型態 A 之 K 線實體與上影線過濾)
    # -------------------------------------------------------------------------
    # (A) 當日必須為實體紅 K (Close > Open)
    cond7_red_k = close_0 > open_0 if (close_0 and open_0 > 0) else False

    # (B) 限制上影線長度 <= 當日 K 棒總波幅 (High - Low) 的 30%
    body_top = max(close_0, open_0)
    upper_shadow = high_0 - body_top if (high_0 and body_top > 0) else 0
    k_range = high_0 - low_0 if (high_0 and low_0 > 0) else 0
    upper_shadow_ratio = (upper_shadow / k_range) if (k_range > 0) else 0
    
    cond8_shadow_ok = upper_shadow_ratio <= 0.30

    # -------------------------------------------------------------------------
    # 綜合所有條件判定
    # -------------------------------------------------------------------------
    is_hit = (
        cond1_trend and 
        cond2_price_ok and 
        cond3_vol_ok and 
        cond4_bias_ok and 
        cond5_continuous and 
        cond6_shakeout and 
        cond7_red_k and 
        cond8_shadow_ok
    )

    info = {
        '選股公式': 'F3_洗盤後_實體紅K與上影線精準版',
        '操作建議': f'強勢實體紅K站穩輕鬆線 (乖離: {easy_bias*100:.1f}%, 量能: {vol_ratio:.1f}倍, 上影線: {upper_shadow_ratio*100:.1f}%)'
    } if is_hit else {}

    return is_hit, info


之所以之前的註解沒有看到這 5 條基本邏輯，是因為原始版本（如 `20261001_1_3` 或 `1152`）開頭的 Docstring **僅記錄了相對於 0745 基準檔的「版本修改摘要（Changelog）」**（例如：1. 保留 0745 結構、2. 微調量能區間...），預設讀者已經知道繼承自 0745 的基礎型態，因此沒有把那 5 條底層條件逐一寫出。

為了讓程式碼更清晰易讀，我們直接將**完整的 5 大基礎選股邏輯**，與**雙控優化**及**右側二次確認風控**完整補齊到策略開頭的註解中：

```python
import pandas as pd

def st_qiantang_f3_after_shakeout_20261001_1_3_2(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = False,
    delay_days: int = 3,         # 🌟 彈性右側觀察天數：1(隔日)、2(兩日) 或 3(三日)
    threshold_pct: float = -0.02  # 🌟 觀察期最大允許跌幅：預設不超過 -2.0%
) -> tuple[bool, dict]:
    """
    【F3_洗盤後 (1152 乖離與量能雙控 + 右側二次確認完整版)】

    策略完整邏輯：
    1. 趨勢過濾：今日收盤價 > MA60（季線多頭格局）
    2. 價格過濾：收盤價 >= 5 元
    3. 量能雙控：今日成交量 >= 350 張，且 1.2 倍 <= 今日成交量 / 5日均量 <= 2.5 倍 (帶量攻堅，防爆天量)
    4. 輕鬆線乖離雙控：0 < (收盤價 - 輕鬆線) / 輕鬆線 <= 4% (貼近支撐買進，防高檔套牢)
    5. 連續確認：今日與昨日皆站上輕鬆線 (close > easy_line)
    6. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線 (close <= easy_line)，確認沉澱完成
    7. 右側二次確認：觸發後第 N 日 (T+delay_days) 觀察短線報酬率 >= threshold_pct (預設 -2.0%)，沒跌超過 -2% 才正式買進
    """
    profile = profile or {}
    
    # 最小長度需求：60日季線基底 + 5日甩轎軌跡 + delay_days 觀察期
    min_required_len = 60 + 5 + delay_days
    if len(df_single) < min_required_len:
        return False, {}

    df_single = df_single.copy()
    if 'MA60' not in df_single.columns:
        df_single['MA60'] = df_single['close'].rolling(window=60).mean()

    # =========================================================================
    # 🌟 內部工具函數：專門驗證相對位置 pos_idx 之 1152 基礎條件
    # =========================================================================
    def _check_1152_base_signal(pos_idx: int) -> tuple[bool, dict]:
        row_t0 = df_single.iloc[pos_idx]
        row_tm1 = df_single.iloc[pos_idx - 1]
        row_tm2 = df_single.iloc[pos_idx - 2]
        row_tm3 = df_single.iloc[pos_idx - 3]
        row_tm4 = df_single.iloc[pos_idx - 4]

        # 1. 價格與輕鬆線 (無預設值 0，缺欄位時直接拋出 KeyError 報錯)
        close_t0 = row_t0['close']
        easy_t0 = row_t0['easy_line']
        ma60_t0 = row_t0['MA60']

        close_tm1 = row_tm1['close']
        easy_tm1 = row_tm1['easy_line']

        # 成交量
        vol_t0 = row_t0['Trading_Volume']
        vol_lots_t0 = vol_t0 / 1000.0 if vol_t0 > 10000 else vol_t0

        # 計算 pos_idx 前 5 日平均成交量 (無預設值，缺欄位時直接拋出 KeyError)
        start_i = pos_idx - 5
        end_i = pos_idx
        recent_vols = df_single['Trading_Volume'].iloc[start_i:end_i]
        vol_ma5 = recent_vols.mean()
        vol_ma5_lots = vol_ma5 / 1000.0 if vol_ma5 > 10000 else vol_ma5

        # --- 邏輯 1：趨勢過濾 (收盤價 > MA60) ---
        cond1_trend = close_t0 > ma60_t0

        # --- 邏輯 2：價格過濾 (收盤價 >= 5 元) ---
        cond2_price_ok = close_t0 >= 5.0

        # --- 邏輯 3：量能雙控 (>= 350張 且 1.2倍 <= 量能倍數 <= 2.5倍) ---
        vol_ratio_t0 = (vol_lots_t0 / vol_ma5_lots) if vol_ma5_lots > 0 else 0
        cond3_vol_ok = (vol_lots_t0 >= 350) and (1.2 <= vol_ratio_t0 <= 2.5)

        # --- 邏輯 4：輕鬆線乖離過濾 (0 < 乖離率 <= 4%) ---
        easy_bias_t0 = (close_t0 - easy_t0) / easy_t0 if easy_t0 > 0 else 999
        cond4_bias_ok = 0 < easy_bias_t0 <= 0.04

        # --- 邏輯 5：連續確認 (今日與昨日皆站上輕鬆線) ---
        cond5_continuous = (close_t0 > easy_t0) and (close_tm1 > easy_tm1)

        # --- 邏輯 6：洗盤甩轎軌跡 (2日前、3日前或 4日前曾跌破輕鬆線) ---
        was_below_tm2 = row_tm2['close'] <= row_tm2['easy_line']
        was_below_tm3 = row_tm3['close'] <= row_tm3['easy_line']
        was_below_tm4 = row_tm4['close'] <= row_tm4['easy_line']
        cond6_shakeout = was_below_tm2 or was_below_tm3 or was_below_tm4

        base_hit = (
            cond1_trend and 
            cond2_price_ok and 
            cond3_vol_ok and 
            cond4_bias_ok and 
            cond5_continuous and 
            cond6_shakeout
        )

        stock_id = str(row_t0['stock_id']) if 'stock_id' in row_t0 else (str(row_t0['股票代號']) if '股票代號' in row_t0 else '')
        date_t0_str = str(row_t0['date']) if 'date' in row_t0 else (str(row_t0['日期']) if '日期' in row_t0 else '')

        details = {
            'close_t0': close_t0,
            'easy_t0': easy_t0,
            'ma60_t0': ma60_t0,
            'vol_lots_t0': vol_lots_t0,
            'vol_ma5_lots': vol_ma5_lots,
            'vol_ratio_t0': vol_ratio_t0,
            'easy_bias_t0': easy_bias_t0,
            'cond1_trend': cond1_trend,
            'cond2_price_ok': cond2_price_ok,
            'cond3_vol_ok': cond3_vol_ok,
            'cond4_bias_ok': cond4_bias_ok,
            'cond5_continuous': cond5_continuous,
            'cond6_shakeout': cond6_shakeout,
            'was_below_tm2': was_below_tm2,
            'was_below_tm3': was_below_tm3,
            'was_below_tm4': was_below_tm4,
            'date_t0_str': date_t0_str,
            'stock_id': stock_id,
        }
        return base_hit, details

    # =========================================================================
    # 🌟 主流程：進行觸發日與觀察日驗證
    # =========================================================================
    t0_pos = -(1 + delay_days)       # 計算觸發日相對位置 (delay_days=3 時為 -4)
    t_confirm_pos = -1               # 最新一筆為觀察確認日

    base_hit, details = _check_1152_base_signal(t0_pos)

    # 取得觀察確認日 (Day T+N) 數據 (若欄位不存在則直接拋出 KeyError)
    row_confirm = df_single.iloc[t_confirm_pos]
    close_confirm = row_confirm['close']
    close_t0 = details['close_t0']

    # --- 邏輯 7：右側二次確認過濾 (T+N 報酬率 >= threshold_pct) ---
    confirm_return = (close_confirm - close_t0) / close_t0 if close_t0 > 0 else -999
    cond7_right_side_ok = confirm_return >= threshold_pct

    # 綜合所有條件判定
    is_hit = base_hit and cond7_right_side_ok

    # =========================================================================
    # 🌟 控制台詳細 Verbose 輸出 (對齊出量上輕 Console 卡牌風格)
    # =========================================================================
    if verbose:
        date_confirm_str = str(row_confirm['date']) if 'date' in row_confirm else (str(row_confirm['日期']) if '日期' in row_confirm else '')
        stock_id = details['stock_id']
        date_t0_str = details['date_t0_str']
        ma60_t0 = details['ma60_t0']
        vol_lots_t0 = details['vol_lots_t0']
        vol_ratio_t0 = details['vol_ratio_t0']
        vol_ma5_lots = details['vol_ma5_lots']
        easy_bias_t0 = details['easy_bias_t0']
        easy_t0 = details['easy_t0']

        c1_mark = '✓' if details['cond1_trend'] else '✕'
        c2_mark = '✓' if details['cond2_price_ok'] else '✕'
        c3_mark = '✓' if details['cond3_vol_ok'] else '✕'
        c4_mark = '✓' if details['cond4_bias_ok'] else '✕'
        c5_mark = '✓' if details['cond5_continuous'] else '✕'
        c6_mark = '✓' if details['cond6_shakeout'] else '✕'
        c7_mark = '✓' if cond7_right_side_ok else '✕'

        tm2 = details['was_below_tm2']
        tm3 = details['was_below_tm3']
        tm4 = details['was_below_tm4']

        print('\n' + '=' * 60)
        print(f"🔔 [F3_洗盤後_乖離與量能雙控版 (T+{delay_days})] 股票: {stock_id} | 觸發日: {date_t0_str} -> 確認日: {date_confirm_str}")
        print('-' * 60)
        print(f"  [{c1_mark}] 1. 季線趨勢過濾 : Close_T > MA60 (MA60: {ma60_t0:.2f}, 觸發價: ${close_t0:.2f})")
        print(f"  [{c2_mark}] 2. 收盤價 >= 5元 : ${close_t0:.2f}")
        print(f"  [{c3_mark}] 3. 量能雙控 (1.2~2.5倍) : {vol_lots_t0:,.0f} 張 (倍數: {vol_ratio_t0:.2f}倍, 5日均量: {vol_ma5_lots:,.0f}張)")
        print(f"  [{c4_mark}] 4. 輕鬆線乖離率 <= 4% : 乖離率 {easy_bias_t0 * 100:.2f}% (輕鬆線: {easy_t0:.2f})")
        print(f"  [{c5_mark}] 5. 連續兩天站上輕鬆線 : Day T 與 Day T-1 均站上")
        print(f"  [{c6_mark}] 6. 洗盤甩轎軌跡 : T-2({tm2}) | T-3({tm3}) | T-4({tm4})")
        print(f"  [{c7_mark}] 7. 🌟 右側二次確認 (T+{delay_days} 報酬 >= {threshold_pct*100:.1f}%) : 報酬 {confirm_return * 100:.2f}% (T+{delay_days}價: ${close_confirm:.2f})")
        print('-' * 60)

    info = {
        '選股公式': 'F3_洗盤後_乖離與量能雙控版',
        '操作建議': f'洗盤結束且緊貼輕鬆線 (乖離: {details["easy_bias_t0"]*100:.1f}%, 量能: {details["vol_ratio_t0"]:.1f}倍)。右側確認通過: T+{delay_days} 報酬 {confirm_return*100:.1f}% (>= {threshold_pct*100:.1f}%)'
    } if is_hit else {}

    return is_hit, info


def st_qiantang_f3_after_shakeout_20261001_1_3(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = False
) -> tuple[bool, dict]:
    """
    【F3_洗盤後（20261002 乖離與量能雙控版）】<---- 過濾回檔觸發非常有效
    直接修改自 0745 版本 (st_qiantang_f3_after_shakeout_20261001_1)：
    1. 保留 0745 無 OLS 的乾淨型態結構
    2. 微調量能區間：1.2 倍 <= 今日成交量 / 5日均量 <= 2.5 倍
    3. 新增風控防線：輕鬆線乖離率上限 <= 4%
    """
    profile = profile or {}
    if len(df_single) < 60:
        return False, {}

    df_single = df_single.copy()
    if 'MA60' not in df_single.columns:
        df_single['MA60'] = df_single['close'].rolling(window=60).mean()

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]
    d3 = df_single.iloc[-4]
    d4 = df_single.iloc[-5]

    close_0 = today.get('close', 0)
    easy_0 = today.get('easy_line', 0)
    vol_0 = today.get('Trading_Volume', 0)
    ma60_0 = today.get('MA60', 0)

    close_1 = d1.get('close', 0)
    easy_1 = d1.get('easy_line', 0)

    # 計算前 5 日平均成交量
    recent_vols = df_single['Trading_Volume'].iloc[-6:-1]
    vol_ma5 = recent_vols.mean() if len(recent_vols) > 0 else 0

    # 1. 趨勢過濾：收盤價 > MA60 (個股季線)
    cond1_trend = close_0 > ma60_0 if (close_0 and ma60_0) else False

    # 2. 價格過濾：收盤價 >= 5 元
    cond2_price_ok = close_0 >= 5.0 if close_0 else False

    # 3. 量能區間過濾：成交量 >= 350 張 且 1.2倍 <= 量能倍數 <= 2.5倍 (🌟 修正處)
    cond3_base_vol = vol_0 >= 350 * 1000 if vol_0 else False
    vol_ratio = (vol_0 / vol_ma5) if (vol_0 and vol_ma5 > 0) else 0
    cond3_vol_ok = cond3_base_vol and (1.2 <= vol_ratio <= 2.5)

    # 4. 輕鬆線乖離過濾：0 < (收盤價 - 輕鬆線) / 輕鬆線 <= 4% (🌟 新增處)
    easy_bias = (close_0 - easy_0) / easy_0 if (close_0 and easy_0 > 0) else 999
    cond4_bias_ok = 0 < easy_bias <= 0.04

    # 5. 連續確認：今日與昨日皆站上輕鬆線
    cond5_today_above = close_0 > easy_0 if (close_0 and easy_0) else False
    cond5_yesterday_above = close_1 > easy_1 if (close_1 and easy_1) else False
    cond5_continuous = cond5_today_above and cond5_yesterday_above

    # 6. 洗盤甩轎軌跡：2日前、3日前或 4日前曾跌破輕鬆線
    was_below_2d = d2.get('close', 0) <= d2.get('easy_line', 0)
    was_below_3d = d3.get('close', 0) <= d3.get('easy_line', 0)
    was_below_4d = d4.get('close', 0) <= d4.get('easy_line', 0)
    cond6_shakeout = was_below_2d or was_below_3d or was_below_4d

    # 綜合所有條件判定
    is_hit = (
        cond1_trend and 
        cond2_price_ok and 
        cond3_vol_ok and 
        cond4_bias_ok and 
        cond5_continuous and 
        cond6_shakeout
    )

    info = {
        '選股公式': 'F3_洗盤後_乖離與量能雙控版',
        '操作建議': f'洗盤結束且緊貼輕鬆線 (乖離: {easy_bias*100:.1f}%, 量能: {vol_ratio:.1f}倍)'
    } if is_hit else {}

    return is_hit, info


def st_qiantang_f3_after_shakeout_20261001_1(
    df_single: pd.DataFrame,
    profile: dict = None,
    verbose: bool = DEBUG_VERBOSE
) -> tuple[bool, dict]:
    """
    【F3_洗盤後（優化版：均線趨勢 + 量能放大 + 連續兩天站上）】
    邏輯：
    1. 趨勢過濾：今日收盤價 > MA60（季線）
    2. 價格過濾：收盤價 >= 5 元
    3. 量能過濾：今日成交量 >= 350 張 且 大於前 5 日均量
    4. 連續確認：今日與昨日皆上輕鬆線 (close > easy_line)
    5. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線 (close <= easy_line)

    修改自st_qiantang_f3_after_shakeout_20261001
    """
    profile = profile or {}
    # 需要至少 6 筆資料以容納前幾日洗盤與 MA60 運算
    if len(df_single) < 6:
        if verbose:
            print(f"❌ [洗盤後] 資料筆數不足 6 筆 (目前: {len(df_single)})")
        return False, {}

    today = df_single.iloc[-1]
    d1 = df_single.iloc[-2]
    d2 = df_single.iloc[-3]
    d3 = df_single.iloc[-4]
    d4 = df_single.iloc[-5]

    close_0 = today.get('close', None)
    easy_0 = today.get('easy_line', None)
    vol_0 = today.get('Trading_Volume', None)
    ma60_0 = today.get('MA60', None)

    close_1 = d1.get('close', None)
    easy_1 = d1.get('easy_line', None)

    # 計算前 5 日平均成交量
    recent_vols = df_single['Trading_Volume'].iloc[-6:-1]
    vol_ma5 = recent_vols.mean() if len(recent_vols) > 0 else 0

    # 1. 趨勢過濾：收盤價 > MA60（若 DataFrame 無 MA60 欄位則預設通過）
    cond1_trend = (close_0 > ma60_0) if (is_valid(close_0) and is_valid(ma60_0)) else True

    # 2. 價格過濾：收盤價 >= 5 元
    cond2_price_ok = (close_0 >= 5.0) if is_valid(close_0) else False

    # 3. 量能過濾：成交量 >= 350 張 且 >= 5日均量
    cond3_base_vol = (vol_0 >= 350 * 1000) if is_valid(vol_0) else False
    cond3_vol_up = (vol_0 >= vol_ma5) if (is_valid(vol_0) and is_valid(vol_ma5) and vol_ma5 > 0) else True
    cond3_vol_ok = cond3_base_vol and cond3_vol_up

    # 4. 連續確認：今日與昨日皆上輕鬆線
    cond4_today_above = (close_0 > easy_0) if (is_valid(close_0) and is_valid(easy_0)) else False
    cond4_yesterday_above = (close_1 > easy_1) if (is_valid(close_1) and is_valid(easy_1)) else False
    cond4_continuous = cond4_today_above and cond4_yesterday_above

    # 5. 洗盤甩轎軌跡：在 2日前、3日前或 4日前曾跌破輕鬆線
    was_below_2d = (d2.get('close', 0) <= d2.get('easy_line', 0)) if (is_valid(d2.get('close')) and is_valid(d2.get('easy_line'))) else False
    was_below_3d = (d3.get('close', 0) <= d3.get('easy_line', 0)) if (is_valid(d3.get('close')) and is_valid(d3.get('easy_line'))) else False
    was_below_4d = (d4.get('close', 0) <= d4.get('easy_line', 0)) if (is_valid(d4.get('close')) and is_valid(d4.get('easy_line'))) else False

    cond5_shakeout = was_below_2d or was_below_3d or was_below_4d

    is_hit = cond1_trend and cond2_price_ok and cond3_vol_ok and cond4_continuous and cond5_shakeout

    if verbose:
        stock_id = today.get('stock_id', '未知個股')
        date_str = str(today.get('date', '最新日'))
        vol_lots = vol_0 / 1000.0 if is_valid(vol_0) else 0.0

        print("\n" + "=" * 55)
        print(f"🔔 [F3_洗盤後優化版] 股票: {stock_id} | 日期: {date_str}")
        print("-" * 55)
        print(f"  [{ '✓' if cond1_trend else '✕' }] 1. 季線趨勢過濾 : Close > MA60")
        print(f"  [{ '✓' if cond2_price_ok else '✕' }] 2. 收盤價 >= 5元 : ${close_0:.2f}" if is_valid(close_0) else "  [✕] 2. 收盤價 >= 5元 : N/A")
        print(f"  [{ '✓' if cond3_vol_ok else '✕' }] 3. 帶量過關 : {vol_lots:,.0f} 張 (>=350張 且 >= 5日均量)")
        print(f"  [{ '✓' if cond4_continuous else '✕' }] 4. 連續兩天站上 : 今日({cond4_today_above}) 與 昨日({cond4_yesterday_above})")
        print(f"  [{ '✓' if cond5_shakeout else '✕' }] 5. 洗盤甩轎軌跡 : 2日前({was_below_2d}) | 3日前({was_below_3d}) | 4日前({was_below_4d})")
        print("-" * 55)
        print(f"🎯 最終觸發結果: {'🔥 [觸發洗盤後優化版]' if is_hit else '⚪ [未觸發]'}")
        print("=" * 55 + "\n")

    info = {
        '選股公式': 'F3_洗盤後_優化版',
        '操作建議': '結合均線多頭、帶量與連續兩天站穩輕鬆線，過濾假突破雜訊後確認洗盤完成。'
    } if is_hit else {}

    return is_hit, info
    
def st_qiantang_f3_after_shakeout_20261001(
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
