# 1. Python 標準函式庫 (Standard Libraries)
from datetime import datetime, timedelta
import time

# 2. 第三方套件 (Third-Party Packages)
from FinMind.data import DataLoader
import numpy as np
import pandas as pd

# 3. 自訂函數庫 (Third-Party Packages)
from .strategy_utils import check_recent_gap, check_volume_condition, calculate_ols_slope_and_r2

def st_u_bottom(df_single, market_above_ma240=True):
  """U底籌碼沉澱突破 (整合 OLS 擬合過濾；跳空與量縮改為純輸出檢測)

  修改自st_u_bottom_2026073101, 增加OLS 迴歸斜率 >= 0.5% 且 R平方 >= 0.6 (走勢平滑)。5日內量縮與跳空的判斷
  ======================================================================
  一、 策略核心邏輯與設計精神 (Strategy Overview)
  ======================================================================
  - 核心觸發：以右側突破 (BUY) 作為第一主動觸發點。
  - 嚴格年線過濾：要求當下年線利用 OLS 迴歸斜率 >= 0.5% 且 R平方 >= 0.6 (走勢平滑)。
  - 季線扣抵過濾：要求當前季線（MA60）未來 20 日的扣抵包袱不得過高。
  - 動態特徵輸出：5日內跳空與量縮狀態改為純輸出，不影響進場判定。
  """
  print(
      f"\n 執行st_u_bottom, 目前是否在年線上"
      f" {market_above_ma240}%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%"
  )

  # 🌟 核心阻擋：若大盤在年線之下，右側突破策略直接不予觸發
  if not market_above_ma240:
    return False, {}

  LOOKBACK_DAYS = 60  # 固定回溯天數為 60 個交易日
  SEDIMENT_COUNT_DAYS = 15  # 要求的沉澱天數
  DISPERSION_THRESHOLD = 0.05  # 中短期均線糾結度
  VOLUME_RATIO_THRESHOLD = 1.3  # 今日量比門檻

  # 設定容忍上限系數
  MAX_DEDUCT_TOLERANCE = 1.15
  MEAN_DEDUCT_TOLERANCE = 1.05

  
  MA240_SLOPE_THRESHOLD = -0.1 # OLS 最小平方法計算過去 20 天 MA240 的斜率條件值
  OLS_R2_THRESHOLD = 0.3 #OLS 最小平方法計算過去 20 天 MA240 的R平方擬合度條件值

  if df_single.empty or len(df_single) < (260 + LOOKBACK_DAYS):
    return False, {}

  # ==================== 1. 共用技術指標計算 ====================
  df_single = df_single.copy()
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()
  df_single['MA240'] = df_single['close'].rolling(240).mean()
  df_single['volume_ma20'] = df_single['Trading_Volume'].rolling(20).mean()

  today = df_single.iloc[-1]

  # 共同基底檢查：必須在年線下方
  is_below_ma240 = today['close'] < today['MA240']

  # 利用 OLS 最小平方法計算過去 20 天 MA240 的斜率與 R平方擬合度
  ma240_window = df_single['MA240'].iloc[-20:]
  ols_slope, ols_r2 = calculate_ols_slope_and_r2(ma240_window)

  # 距離年線乖離率
  dist_ratio = (today['close'] - today['MA240']) / today['MA240']

  # ==================== 2. 季線 (MA60) 精準扣抵分析 ====================
  future_ma60_deduct = df_single['close'].iloc[-60:-40]
  deduct_max = future_ma60_deduct.max()
  deduct_mean = future_ma60_deduct.mean()

  is_ma60_deduct_favorable = (
      deduct_max <= today['close'] * MAX_DEDUCT_TOLERANCE
      and deduct_mean <= today['close'] * MEAN_DEDUCT_TOLERANCE
  )

  # ==================== 3. 階段二：右側突破判定 (今日表態條件) ====================
  # A. 均線糾結度檢查 (5/20/60)
  ma_list = [today['MA5'], today['MA20'], today['MA60']]
  dispersion = (
      (max(ma_list) - min(ma_list)) / min(ma_list) if min(ma_list) > 0 else 1
  )
  is_converged = dispersion < DISPERSION_THRESHOLD

  # B. 帶量轉強檢查
  vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
  is_volume_up = (
      today['Trading_Volume'] > vol_ma5 * VOLUME_RATIO_THRESHOLD
      if vol_ma5 > 0
      else False
  )

  # C. 價值型穩健築底：以 OLS 斜率 >= 0.5% 且 R平方 >= 0.6 作為平滑上升保證
  is_smooth_uptrend = ols_slope >= MA240_SLOPE_THRESHOLD and ols_r2 >= OLS_R2_THRESHOLD

  # D. 右側價格確認（當日收盤價不得為 5 日內最低點）
  df_single['min_close_5d'] = df_single['close'].rolling(5).min()
  is_not_lowest_5d = today['close'] > df_single['min_close_5d'].iloc[-1]

  # 🌟 E. 調用獨立函數：檢測 5 日內跳空與量縮狀態（純輸出用，不作為阻擋條件）
  recent_6d_slice = df_single.iloc[-6:].copy()
  has_5d_gap = check_recent_gap(recent_6d_slice)
  has_5d_surge, max_5d_vol_ratio = check_volume_condition(
    df_single.iloc[-5:].copy(), threshold=2.0, is_surge=True
  )

  # 今日是否符合右側突破的表態條件（不再包含跳空/量縮阻擋）
  is_today_right_hit = (
      is_below_ma240
      and is_converged
      and is_volume_up
      and is_smooth_uptrend
      and is_not_lowest_5d
      and is_ma60_deduct_favorable
  )

  # ==================== 4. 核心反向回溯驗證：檢查歷史扎實沉澱 ====================
  has_preceding_sediment = False
  validated_sediment_days = 0

  if is_today_right_hit:
    history_window = df_single.iloc[-(LOOKBACK_DAYS + 1) : -1]
    sediment_count = 0

    for i in range(len(history_window)):
      row = history_window.iloc[i]
      hist_below = row['close'] < row['MA240']

      idx_in_full = len(df_single) - LOOKBACK_DAYS + i
      if idx_in_full >= 20:
        hist_window_sub = df_single['MA240'].iloc[idx_in_full - 19 : idx_in_full + 1]
        hist_slope, _ = calculate_ols_slope_and_r2(hist_window_sub)
      else:
        hist_slope = 0

      hist_downward = hist_slope >= -0.5
      hist_dist = (row['close'] - row['MA240']) / row['MA240']
      hist_discounted = -0.25 <= hist_dist <= -0.02

      if i >= 9:
        sub_close = history_window['close'].iloc[i - 9 : i + 1]
        sub_cv = (
            sub_close.std() / sub_close.mean() if sub_close.mean() > 0 else 1
        )
        hist_stabilized = sub_cv <= 0.02
      else:
        hist_stabilized = False

      if hist_below and hist_downward and hist_stabilized and hist_discounted:
        sediment_count += 1

    if sediment_count >= SEDIMENT_COUNT_DAYS:
      has_preceding_sediment = True
      validated_sediment_days = sediment_count

  # ==================== 5. 最終狀態封裝與輸出分流 ====================
  if is_today_right_hit and has_preceding_sediment:
    strategy_stage = (
        f'【築底驗證成功】OLS斜率平滑(R2={round(ols_r2,2)})➔買進'
    )
    action_signal = 'BUY'
    is_hit = True
  else:
    strategy_stage = (
        '未觸發有效買進訊號 (OLS平滑度不足、季線扣抵過高或沉澱不足)'
    )
    action_signal = 'NONE'
    is_hit = False

  recent_10d = df_single['close'].iloc[-10:]
  price_cv = (
      recent_10d.std() / recent_10d.mean() if recent_10d.mean() > 0 else 0
  )
  stop_loss = 0.2

  info = {
      '收盤': today['close'],
      '策略狀態': strategy_stage,
      '停損價': f'{stop_loss}%',
      '距離年線': f'{round(dist_ratio * 100, 2)}%',
      '年線OLS斜率': f'{round(ols_slope, 2)}%',
      '年線R平方': round(ols_r2, 2),
      '5日內曾有跳空': '有' if has_5d_gap else '無',
      '5日內曾有量縮': (
          f'有 (最低量比 {min_5d_vol_ratio}x)'
          if has_5d_surge
          else f'無 (最低量比 {min_5d_vol_ratio}x)'
      ),
      '季線扣抵均值': round(deduct_mean, 2),
      '季線扣抵最高': round(deduct_max, 2),
      '近10日價格波動度': f'{round(price_cv * 100, 2)}%',
      '中短期糾結度': f'{round(dispersion * 100, 2)}%',
      '今日量比': (
          f'{round(today["Trading_Volume"]/vol_ma5, 2) if vol_ma5 > 0 else 0}x'
      ),
      '沉澱天數': validated_sediment_days,
      '前置沉澱扎實度評估': (
          f'{validated_sediment_days}/{LOOKBACK_DAYS}, 門檻{SEDIMENT_COUNT_DAYS}'
      ),
      '訊號動作': action_signal,
  }

  return is_hit, info


def st_u_bottom_2026073101(df_single, market_above_ma240=True):
  """U底籌碼沉澱突破 (含修正後的精準季線扣抵過濾)

  修正自st_u_bottom_2026073001, 增加季線扣抵值的判斷, 再增加大盤年線判斷
  回測資料yf_test_st_u_bottom_range_2015-01-01_to_2025-09-30_20260731_0020加上大盤年線判斷
  ======================================================================
  一、 策略核心邏輯與設計精神 (Strategy Overview)
  ======================================================================
  - 核心觸發：以右側突破 (BUY) 作為第一主動觸發點。
  - 嚴格年線過濾：要求當下年線 20 日斜率必須 >= 0.0% (平轉或向上)，拒絕空頭接刀。
  - 季線扣抵過濾：要求當前季線（MA60）未來 20 日的扣抵包袱不得過高（不超過現價的容忍上限）。
  - 反向回溯驗證：當右側突破成立時，固定回溯過去 60 個交易日（約 3 個月），
    檢查是否經歷過扎實的左側籌碼沉澱（累積符合條件達 15 天以上）。
  - 風控目標：確保打底扎實、拒絕短線假突破與高風險深水區回檔。
  """
  print(f"\n 執行st_u_bottom, 目前是否在年線上 {market_above_ma240}%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
  
  # 🌟 核心阻擋：若大盤在年線之下，右側突破策略直接不予觸發
  if not market_above_ma240:
    return False, {}
   
  LOOKBACK_DAYS = 60    # 固定回溯天數為 60 個交易日（約 3 個月）  
  SEDIMENT_COUNT_DAYS = 15 # 要求的沉澱天數
  DISPERSION_THRESHOLD = 0.05 # 中短期均線糾結度 0.042
  VOLUME_RATIO_THRESHOLD = 1.3 # 今日量比門檻 1.4

  # 設定容忍上限系數（允許扣抵價高於現價，但限制在合理安全範圍內）
  MAX_DEDUCT_TOLERANCE = 1.15  # 扣抵最大值最多比現價高 15%
  MEAN_DEDUCT_TOLERANCE = 1.05 # 扣抵平均值最多比現價高 5%

  # 需要足夠長歷史資料計算年線(240) + 季線(60) + 回溯天數(60)
  if df_single.empty or len(df_single) < (260 + LOOKBACK_DAYS):
    return False, {}

  # ==================== 1. 共用技術指標計算 ====================
  df_single = df_single.copy()
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()
  df_single['MA240'] = df_single['close'].rolling(240).mean()

  today = df_single.iloc[-1]

  # 共同基底檢查：必須在年線下方
  is_below_ma240 = today['close'] < today['MA240']

  # 年線 20 日斜率
  ma240_20d_ago = df_single['MA240'].iloc[-21]
  ma_slope_20d = (
      (today['MA240'] - ma240_20d_ago) / ma240_20d_ago
      if ma240_20d_ago > 0
      else 0
  )

  # 距離年線乖離率
  dist_ratio = (today['close'] - today['MA240']) / today['MA240']

  # ==================== 2. 季線 (MA60) 精準扣抵分析 ====================
  # 正確對應未來 20 日準備扣掉的歷史區間 (MA60 往前推 60~40 天)
  future_ma60_deduct = df_single['close'].iloc[-60:-40]
  
  deduct_max = future_ma60_deduct.max()
  deduct_mean = future_ma60_deduct.mean()



  # 季線扣抵過濾條件：扣抵值可以比現價高，但「不可以高過收盤價太多」
  is_ma60_deduct_favorable = (
      (deduct_max <= today['close'] * MAX_DEDUCT_TOLERANCE) and
      (deduct_mean <= today['close'] * MEAN_DEDUCT_TOLERANCE)
  )

  # ==================== 3. 階段二：右側突破判定 (今日表態條件) ====================
  # A. 均線糾結度檢查 (5/20/60)
  ma_list = [today['MA5'], today['MA20'], today['MA60']]
  dispersion = (
      (max(ma_list) - min(ma_list)) / min(ma_list) if min(ma_list) > 0 else 1
  )
  is_converged = dispersion < DISPERSION_THRESHOLD

  # B. 帶量轉強檢查
  vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
  is_volume_up = (
      today['Trading_Volume'] > vol_ma5 * VOLUME_RATIO_THRESHOLD if vol_ma5 > 0 else False
  )

  # C. 價值型穩健築底：嚴格規定年線斜率必須 >= 0.0 (平轉或向上)
  is_flattening_slope = ma_slope_20d >= 0.0

  # D. 右側價格確認（當日收盤價不得為 5 日內最低點）
  df_single['min_close_5d'] = df_single['close'].rolling(5).min()  
  is_not_lowest_5d = today['close'] > df_single['min_close_5d'].iloc[-1]

  # 今日是否符合右側突破的表態條件
  is_today_right_hit = (
      is_below_ma240
      and is_converged
      and is_volume_up
      and is_flattening_slope
      and is_not_lowest_5d  
      and is_ma60_deduct_favorable  # <--- 修正後的精準季線扣抵防線
  )

  # ==================== 4. 核心反向回溯驗證：檢查歷史扎實沉澱 ====================
  has_preceding_sediment = False
  validated_sediment_days = 0

  if is_today_right_hit:
    history_window = df_single.iloc[-(LOOKBACK_DAYS + 1) : -1]

    sediment_count = 0
    for i in range(len(history_window)):
      row = history_window.iloc[i]
      hist_below = row['close'] < row['MA240']

      idx_in_full = len(df_single) - LOOKBACK_DAYS + i
      if idx_in_full >= 21:
        hist_ma240_ago = df_single['MA240'].iloc[idx_in_full - 21]
        hist_slope = (
            (row['MA240'] - hist_ma240_ago) / hist_ma240_ago
            if hist_ma240_ago > 0
            else 0
        )
      else:
        hist_slope = 0

      hist_downward = hist_slope >= -0.005
      hist_dist = (row['close'] - row['MA240']) / row['MA240']
      hist_discounted = -0.25 <= hist_dist <= -0.02

      if i >= 9:
        sub_close = history_window['close'].iloc[i - 9 : i + 1]
        sub_cv = (
            sub_close.std() / sub_close.mean() if sub_close.mean() > 0 else 1
        )
        hist_stabilized = sub_cv <= 0.02  
      else:
        hist_stabilized = False

      if hist_below and hist_downward and hist_stabilized and hist_discounted:
        sediment_count += 1

    if sediment_count >= SEDIMENT_COUNT_DAYS:
      has_preceding_sediment = True
      validated_sediment_days = sediment_count

  # ==================== 5. 最終狀態封裝與輸出分流 ====================
  if is_today_right_hit and has_preceding_sediment:
    strategy_stage = (
        f'【築底驗證成功】前方經長期沉澱(>={validated_sediment_days}天)➔買進'
    )
    action_signal = 'BUY'
    is_hit = True
  else:
    strategy_stage = (
        f'未觸發有效買進訊號 (無效突破、季線扣抵過高或沉澱不足{SEDIMENT_COUNT_DAYS}天)'
    )
    action_signal = 'NONE'
    is_hit = False

  recent_10d = df_single['close'].iloc[-10:]
  price_cv = (
      recent_10d.std() / recent_10d.mean() if recent_10d.mean() > 0 else 0
  )

  stop_loss = 0.2
  
  info = {
      '收盤': today['close'],
      '策略狀態': strategy_stage,
      '停損價': f"{stop_loss}%",
      '距離年線': f"{round(dist_ratio * 100, 2)}%",
      '年線20日斜率': f"{round(ma_slope_20d * 100, 2)}%",
      '季線扣抵均值': round(deduct_mean, 2),    # 新增輸出：扣抵平均價
      '季線扣抵最高': round(deduct_max, 2),     # 新增輸出：扣抵最高價
      '近10日價格波動度': f"{round(price_cv * 100, 2)}%",
      '中短期糾結度': f"{round(dispersion * 100, 2)}%",
      '今日量比': (
          f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x"
      ),
      '沉澱天數': validated_sediment_days,
      '前置沉澱扎實度評估': (
          (f'{validated_sediment_days}/{LOOKBACK_DAYS}, 門檻{SEDIMENT_COUNT_DAYS}')
      ),
      '訊號動作': action_signal,
  }
  
  return is_hit, info


def st_u_bottom_2026073002(df_single, market_above_ma240=True):
  """U底籌碼沉澱突破
     穩健築底反向回溯60日驗證籌碼是否沉澱

     修正自st_u_bottom_2026073001, 增加大盤在年線以上或以下的判斷, 年線以下就不執行策略
      
  ======================================================================
  一、 策略核心邏輯與設計精神 (Strategy Overview)
  ======================================================================
  - 核心觸發：以右側突破 (BUY) 作為第一主動觸發點。
  - 嚴格年線過濾：要求當下年線 20 日斜率必須 >= 0.0% (平轉或向上)，拒絕空頭接刀。
  - 反向回溯驗證：當右側突破成立時，固定回溯過去 60 個交易日（約 3 個月），
    檢查是否經歷過扎實的左側籌碼沉澱（累積符合條件達 10 天以上）。
  - 風控目標：確保打底扎實、拒絕短線假突破與高風險深水區回檔。

  ======================================================================
  二、 技術指標與共用基準計算 (Technical Indicators)
  ======================================================================
  - 移動平均線：MA5、MA20、MA60、MA240 (年線)
  - 基礎位置檢查：
    * 價格相對年線位置：收盤價必須在年線下方 (`today['close'] < today['MA240']`)
    * 年線 20 日斜率 (`ma_slope_20d`)：過去 21 個交易日的年線變化率
    * 距離年線乖離率 (`dist_ratio`)：(收盤價 - MA240) / MA240
  - 扣抵分析：計算未來 20 日的扣抵斜率 (`deduct_slope`)

  ======================================================================
  三、 階段二：右側突破判定 (Today's Breakout Conditions)
  ======================================================================
  【今日表態觸發條件 (is_today_right_hit)】
    - 均線糾結度 (`dispersion`)：MA5、MA20、MA60 波動範圍小於 5% (`< 0.05`)
    - 帶量轉強 (`is_volume_up`)：今日成交量大於 5 日均量的 1.3 倍以上
    - 年線平轉或向上 (`is_flattening_slope`)：MA240 20日斜率 >= 0.0%
    - 5日價格確認 (`is_not_lowest_5d`)：今日收盤價非 5 日內最低點，具備止穩反彈特徵

  ======================================================================
  四、 核心反向回溯驗證：歷史扎實沉澱檢視 (Historical Sediment Check)
  ======================================================================
  - 回溯天數 (`LOOKBACK_DAYS`)：固定回溯過去 60 個交易日。
  - 單日沉澱判定標準 (`sediment_count`)：
    * 歷史價位處於年線下方
    * 歷史年線斜率未強烈下彎 (`hist_slope >= -0.005`)
    * 歷史乖離率位於 -25% 至 -2% 之間
    * 歷史價格波動度壓縮（前 10 日標準差/均值 <= 2%）
  - 扎實度門檻：回溯窗內累積符合上述特徵必須達到 **>= 10 天**，方視為有效沉澱。

  ======================================================================
  五、 最终狀態封裝與輸出分流 (Classification & Output)
  ======================================================================
  - 觸發成功 (`BUY`)：今日右側突破條件成立，且前方經 >= 10 天的扎實長期沉澱。
  - 未觸發 (`NONE`)：無效突破、年線下彎或前置沉澱天數不足。
  - 輸出字典 (`info`)：包含收盤價、策略階段、訊號動作、停損比例、距離年線、
    年線斜率、近10日波動度、中短期糾結度、今日量比及回溯沉澱天數評估。
  ======================================================================


  策略邏輯： - 以右側突破 (BUY) 作為第一主動觸發點。 - 嚴格年線過濾：要求當下年線 20 日斜率必須 >= 0.0% (平轉或向上)，拒絕空頭接刀。 -
  當右側突破成立時，固定回溯過去 60 個交易日（約3個月），檢查是否經歷過扎實的左側籌碼沉澱 (累積至少 10 天以上)。 -
  確保打底扎實、拒絕短線假突破與高風險深水區回檔。
  """
  print(f"\n 執行st_u_bottom, 目前是否在年線上 {market_above_ma240}%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
  
  # 🌟 核心阻擋：若大盤在年線之下，右側突破策略直接不予觸發
  if not market_above_ma240:
    return False, {}
  
  LOOKBACK_DAYS = 60  # 直接寫死回溯天數為 60 個交易日（約 3 個月）  
  SEDIMENT_COUNT_DAYS = 15 #要求的沉澱天數
  DISPERSION_THRESHOLD = 0.042 #中短期均線糾結度
  VOLUME_RATIO_THRESHOLD = 1.4 #今日量比為今日量與20日均量的比值
  
  if df_single.empty or len(df_single) < (260 + LOOKBACK_DAYS):
    return False, {}

  # ==================== 1. 共用技術指標計算 ====================
  df_single = df_single.copy()
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()
  df_single['MA240'] = df_single['close'].rolling(240).mean()

  today = df_single.iloc[-1]

  # 共同基底檢查：必須在年線下方
  is_below_ma240 = today['close'] < today['MA240']

  # 年線 20 日斜率
  ma240_20d_ago = df_single['MA240'].iloc[-21]
  ma_slope_20d = (
      (today['MA240'] - ma240_20d_ago) / ma240_20d_ago
      if ma240_20d_ago > 0
      else 0
  )

  # 距離年線乖離率
  dist_ratio = (today['close'] - today['MA240']) / today['MA240']

  # ==================== 2. 共用核心：未來 20 日扣抵分析 ====================
  future_deduct_series = df_single['close'].iloc[-240:-220]
  deduct_slope = (
      (future_deduct_series.iloc[-1] - future_deduct_series.iloc[0])
      / future_deduct_series.iloc[0]
      if future_deduct_series.iloc[0] > 0
      else 0
  )

  # ==================== 3. 階段二：右側突破判定 (今日表態條件) ====================
  # A. 均線糾結度檢查 (5/20/60)
  ma_list = [today['MA5'], today['MA20'], today['MA60']]
  dispersion = (
      (max(ma_list) - min(ma_list)) / min(ma_list) if min(ma_list) > 0 else 1
  )
  #is_converged = dispersion < 0.05
  is_converged = dispersion < DISPERSION_THRESHOLD

  # B. 帶量轉強檢查
  vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
  #is_volume_up = (
  #    today['Trading_Volume'] > vol_ma5 * 1.3 if vol_ma5 > 0 else False
  #)

  is_volume_up = (
      today['Trading_Volume'] > vol_ma5 * VOLUME_RATIO_THRESHOLD if vol_ma5 > 0 else False
  )

  # C. 價值型穩健築底：嚴格規定年線斜率必須 >= 0.0 (平轉或向上，不開後門)
  is_flattening_slope = ma_slope_20d >= 0.0

  # D. 新增：右側價格確認（當日收盤價不得為 5 日內最低點，必須高於 5 日低點或出現止穩反彈）
  # 計算 5 日內收盤最低價（用於右側反彈確認）
  df_single['min_close_5d'] = df_single['close'].rolling(5).min()  
  is_not_lowest_5d = today['close'] > df_single['min_close_5d'].iloc[-1]

  # 今日是否符合右側突破的表態條件
  is_today_right_hit = (
      is_below_ma240
      and is_converged
      and is_volume_up
      and is_flattening_slope
      and is_not_lowest_5d  # 嚴格過濾 5 日創新低/最低點
  )

  # ==================== 4. 核心反向回溯驗證：檢查歷史扎實沉澱 ====================
  has_preceding_sediment = False
  validated_sediment_days = 0

  if is_today_right_hit:
    # 切片檢視過去 60 天內的歷史 K 線是否符合左側穩健沉澱特徵
    history_window = df_single.iloc[-(LOOKBACK_DAYS + 1) : -1]

    sediment_count = 0
    for i in range(len(history_window)):
      row = history_window.iloc[i]
      hist_below = row['close'] < row['MA240']

      # 計算該歷史點位的 MA240 20日斜率
      idx_in_full = len(df_single) - LOOKBACK_DAYS + i
      if idx_in_full >= 21:
        hist_ma240_ago = df_single['MA240'].iloc[idx_in_full - 21]
        hist_slope = (
            (row['MA240'] - hist_ma240_ago) / hist_ma240_ago
            if hist_ma240_ago > 0
            else 0
        )
      else:
        hist_slope = 0

      # 價值型築底不允許歷史點位呈現強烈下彎
      hist_downward = hist_slope >= -0.005
      hist_dist = (row['close'] - row['MA240']) / row['MA240']
      hist_discounted = -0.25 <= hist_dist <= -0.02

      # 檢查當日價格波動度 (取該日前 10 日，確保價格已充分壓縮收斂)
      if i >= 9:
        sub_close = history_window['close'].iloc[i - 9 : i + 1]
        sub_cv = (
            sub_close.std() / sub_close.mean() if sub_close.mean() > 0 else 1
        )
        hist_stabilized = sub_cv <= 0.02  # 波動度嚴格收斂在 2% 以內
      else:
        hist_stabilized = False

      if hist_below and hist_downward and hist_stabilized and hist_discounted:
        sediment_count += 1

    # 要求回溯窗內累積必須達到至少 SEDIMENT_COUNT_DAYS 天以上的沉澱，才視為扎實築底
    if sediment_count >= SEDIMENT_COUNT_DAYS:
      has_preceding_sediment = True
      validated_sediment_days = sediment_count

  # ==================== 5. 最終狀態封裝與輸出分流 ====================
  if is_today_right_hit and has_preceding_sediment:
    strategy_stage = (
        f'【築底驗證成功】前方經長期沉澱(>={validated_sediment_days}天)➔買進'
    )
    action_signal = 'BUY'
    is_hit = True
  else:
    strategy_stage = (
        f'未觸發有效買進訊號 (無效突破、年線下彎或沉澱不足{SEDIMENT_COUNT_DAYS}天)'
    )
    action_signal = 'NONE'
    is_hit = False

  # 近 10 日價格波動度計算
  recent_10d = df_single['close'].iloc[-10:]
  price_cv = (
      recent_10d.std() / recent_10d.mean() if recent_10d.mean() > 0 else 0
  )

  stop_loss = 0.2
  
  info = {
      '收盤': today['close'],
      '策略狀態': strategy_stage,
      '停損價': f"{stop_loss}%",
      '距離年線': f"{round(dist_ratio * 100, 2)}%",
      '年線20日斜率': f"{round(ma_slope_20d * 100, 2)}%",
      '近10日價格波動度': f"{round(price_cv * 100, 2)}%",
      '中短期糾結度': f"{round(dispersion * 100, 2)}%",
      '今日量比': (
          f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x"
      ),
      '沉澱天數': validated_sediment_days,
      '前置沉澱扎實度評估': (
          (f'{validated_sediment_days}/{LOOKBACK_DAYS}, 門檻{SEDIMENT_COUNT_DAYS}')
      ),
      '訊號動作': action_signal,
  }

  
  #print(f'u_bottom_v2 action:{action_signal} info:{info}')
  return is_hit, info


def st_u_bottom_2026073001(df_single):
  """U底籌碼沉澱突破
     穩健築底反向回溯60日驗證籌碼是否沉澱

  ======================================================================
  一、 策略核心邏輯與設計精神 (Strategy Overview)
  ======================================================================
  - 核心觸發：以右側突破 (BUY) 作為第一主動觸發點。
  - 嚴格年線過濾：要求當下年線 20 日斜率必須 >= 0.0% (平轉或向上)，拒絕空頭接刀。
  - 反向回溯驗證：當右側突破成立時，固定回溯過去 60 個交易日（約 3 個月），
    檢查是否經歷過扎實的左側籌碼沉澱（累積符合條件達 10 天以上）。
  - 風控目標：確保打底扎實、拒絕短線假突破與高風險深水區回檔。

  ======================================================================
  二、 技術指標與共用基準計算 (Technical Indicators)
  ======================================================================
  - 移動平均線：MA5、MA20、MA60、MA240 (年線)
  - 基礎位置檢查：
    * 價格相對年線位置：收盤價必須在年線下方 (`today['close'] < today['MA240']`)
    * 年線 20 日斜率 (`ma_slope_20d`)：過去 21 個交易日的年線變化率
    * 距離年線乖離率 (`dist_ratio`)：(收盤價 - MA240) / MA240
  - 扣抵分析：計算未來 20 日的扣抵斜率 (`deduct_slope`)

  ======================================================================
  三、 階段二：右側突破判定 (Today's Breakout Conditions)
  ======================================================================
  【今日表態觸發條件 (is_today_right_hit)】
    - 均線糾結度 (`dispersion`)：MA5、MA20、MA60 波動範圍小於 5% (`< 0.05`)
    - 帶量轉強 (`is_volume_up`)：今日成交量大於 5 日均量的 1.3 倍以上
    - 年線平轉或向上 (`is_flattening_slope`)：MA240 20日斜率 >= 0.0%
    - 5日價格確認 (`is_not_lowest_5d`)：今日收盤價非 5 日內最低點，具備止穩反彈特徵

  ======================================================================
  四、 核心反向回溯驗證：歷史扎實沉澱檢視 (Historical Sediment Check)
  ======================================================================
  - 回溯天數 (`LOOKBACK_DAYS`)：固定回溯過去 60 個交易日。
  - 單日沉澱判定標準 (`sediment_count`)：
    * 歷史價位處於年線下方
    * 歷史年線斜率未強烈下彎 (`hist_slope >= -0.005`)
    * 歷史乖離率位於 -25% 至 -2% 之間
    * 歷史價格波動度壓縮（前 10 日標準差/均值 <= 2%）
  - 扎實度門檻：回溯窗內累積符合上述特徵必須達到 **>= 10 天**，方視為有效沉澱。

  ======================================================================
  五、 最终狀態封裝與輸出分流 (Classification & Output)
  ======================================================================
  - 觸發成功 (`BUY`)：今日右側突破條件成立，且前方經 >= 10 天的扎實長期沉澱。
  - 未觸發 (`NONE`)：無效突破、年線下彎或前置沉澱天數不足。
  - 輸出字典 (`info`)：包含收盤價、策略階段、訊號動作、停損比例、距離年線、
    年線斜率、近10日波動度、中短期糾結度、今日量比及回溯沉澱天數評估。
  ======================================================================


  策略邏輯： - 以右側突破 (BUY) 作為第一主動觸發點。 - 嚴格年線過濾：要求當下年線 20 日斜率必須 >= 0.0% (平轉或向上)，拒絕空頭接刀。 -
  當右側突破成立時，固定回溯過去 60 個交易日（約3個月），檢查是否經歷過扎實的左側籌碼沉澱 (累積至少 10 天以上)。 -
  確保打底扎實、拒絕短線假突破與高風險深水區回檔。
  """
  
  LOOKBACK_DAYS = 60  # 直接寫死回溯天數為 60 個交易日（約 3 個月）  
  SEDIMENT_COUNT_DAYS = 15 #要求的沉澱天數
  DISPERSION_THRESHOLD = 0.042 #中短期均線糾結度
  VOLUME_RATIO_THRESHOLD = 1.4 #今日量比為今日量與20日均量的比值

  if df_single.empty or len(df_single) < (260 + LOOKBACK_DAYS):
    return False, {}

  # ==================== 1. 共用技術指標計算 ====================
  df_single = df_single.copy()
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()
  df_single['MA240'] = df_single['close'].rolling(240).mean()

  today = df_single.iloc[-1]

  # 共同基底檢查：必須在年線下方
  is_below_ma240 = today['close'] < today['MA240']

  # 年線 20 日斜率
  ma240_20d_ago = df_single['MA240'].iloc[-21]
  ma_slope_20d = (
      (today['MA240'] - ma240_20d_ago) / ma240_20d_ago
      if ma240_20d_ago > 0
      else 0
  )

  # 距離年線乖離率
  dist_ratio = (today['close'] - today['MA240']) / today['MA240']

  # ==================== 2. 共用核心：未來 20 日扣抵分析 ====================
  future_deduct_series = df_single['close'].iloc[-240:-220]
  deduct_slope = (
      (future_deduct_series.iloc[-1] - future_deduct_series.iloc[0])
      / future_deduct_series.iloc[0]
      if future_deduct_series.iloc[0] > 0
      else 0
  )

  # ==================== 3. 階段二：右側突破判定 (今日表態條件) ====================
  # A. 均線糾結度檢查 (5/20/60)
  ma_list = [today['MA5'], today['MA20'], today['MA60']]
  dispersion = (
      (max(ma_list) - min(ma_list)) / min(ma_list) if min(ma_list) > 0 else 1
  )
  #is_converged = dispersion < 0.05
  is_converged = dispersion < DISPERSION_THRESHOLD

  # B. 帶量轉強檢查
  vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
  #is_volume_up = (
  #    today['Trading_Volume'] > vol_ma5 * 1.3 if vol_ma5 > 0 else False
  #)

  is_volume_up = (
      today['Trading_Volume'] > vol_ma5 * VOLUME_RATIO_THRESHOLD if vol_ma5 > 0 else False
  )

  # C. 價值型穩健築底：嚴格規定年線斜率必須 >= 0.0 (平轉或向上，不開後門)
  is_flattening_slope = ma_slope_20d >= 0.0

  # D. 新增：右側價格確認（當日收盤價不得為 5 日內最低點，必須高於 5 日低點或出現止穩反彈）
  # 計算 5 日內收盤最低價（用於右側反彈確認）
  df_single['min_close_5d'] = df_single['close'].rolling(5).min()  
  is_not_lowest_5d = today['close'] > df_single['min_close_5d'].iloc[-1]

  # 今日是否符合右側突破的表態條件
  is_today_right_hit = (
      is_below_ma240
      and is_converged
      and is_volume_up
      and is_flattening_slope
      and is_not_lowest_5d  # 嚴格過濾 5 日創新低/最低點
  )

  # ==================== 4. 核心反向回溯驗證：檢查歷史扎實沉澱 ====================
  has_preceding_sediment = False
  validated_sediment_days = 0

  if is_today_right_hit:
    # 切片檢視過去 60 天內的歷史 K 線是否符合左側穩健沉澱特徵
    history_window = df_single.iloc[-(LOOKBACK_DAYS + 1) : -1]

    sediment_count = 0
    for i in range(len(history_window)):
      row = history_window.iloc[i]
      hist_below = row['close'] < row['MA240']

      # 計算該歷史點位的 MA240 20日斜率
      idx_in_full = len(df_single) - LOOKBACK_DAYS + i
      if idx_in_full >= 21:
        hist_ma240_ago = df_single['MA240'].iloc[idx_in_full - 21]
        hist_slope = (
            (row['MA240'] - hist_ma240_ago) / hist_ma240_ago
            if hist_ma240_ago > 0
            else 0
        )
      else:
        hist_slope = 0

      # 價值型築底不允許歷史點位呈現強烈下彎
      hist_downward = hist_slope >= -0.005
      hist_dist = (row['close'] - row['MA240']) / row['MA240']
      hist_discounted = -0.25 <= hist_dist <= -0.02

      # 檢查當日價格波動度 (取該日前 10 日，確保價格已充分壓縮收斂)
      if i >= 9:
        sub_close = history_window['close'].iloc[i - 9 : i + 1]
        sub_cv = (
            sub_close.std() / sub_close.mean() if sub_close.mean() > 0 else 1
        )
        hist_stabilized = sub_cv <= 0.02  # 波動度嚴格收斂在 2% 以內
      else:
        hist_stabilized = False

      if hist_below and hist_downward and hist_stabilized and hist_discounted:
        sediment_count += 1

    # 要求回溯窗內累積必須達到至少 SEDIMENT_COUNT_DAYS 天以上的沉澱，才視為扎實築底
    if sediment_count >= SEDIMENT_COUNT_DAYS:
      has_preceding_sediment = True
      validated_sediment_days = sediment_count

  # ==================== 5. 最終狀態封裝與輸出分流 ====================
  if is_today_right_hit and has_preceding_sediment:
    strategy_stage = (
        f'【築底驗證成功】前方經長期沉澱(>={validated_sediment_days}天)➔買進'
    )
    action_signal = 'BUY'
    is_hit = True
  else:
    strategy_stage = (
        f'未觸發有效買進訊號 (無效突破、年線下彎或沉澱不足{SEDIMENT_COUNT_DAYS}天)'
    )
    action_signal = 'NONE'
    is_hit = False

  # 近 10 日價格波動度計算
  recent_10d = df_single['close'].iloc[-10:]
  price_cv = (
      recent_10d.std() / recent_10d.mean() if recent_10d.mean() > 0 else 0
  )

  stop_loss = 0.2
  
  info = {
      '收盤': today['close'],
      '策略狀態': strategy_stage,
      '停損價': f"{stop_loss}%",
      '距離年線': f"{round(dist_ratio * 100, 2)}%",
      '年線20日斜率': f"{round(ma_slope_20d * 100, 2)}%",
      '近10日價格波動度': f"{round(price_cv * 100, 2)}%",
      '中短期糾結度': f"{round(dispersion * 100, 2)}%",
      '今日量比': (
          f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x"
      ),
      '沉澱天數': validated_sediment_days,
      '前置沉澱扎實度評估': (
          (f'{validated_sediment_days}/{LOOKBACK_DAYS}, 門檻{SEDIMENT_COUNT_DAYS}')
      ),
      '訊號動作': action_signal,
  }

  
  #print(f'u_bottom_v2 action:{action_signal} info:{info}')
  return is_hit, info

def st_bottom_v_turn(df_single, market_above_ma240=True):
  """V轉選股
  【條件一】為穩健築底與短多排列，【條件二】為強勢突破與季線黃金交叉 

  回測資料yf_test_st_bottom_v_turn_range_2015-01-01_to_2025-09-30_20260730_2349加上大盤年線判斷

  ======================================================================
  一、 策略核心邏輯與設計精神 (Strategy Overview)
  ======================================================================
  - 核心目標：捕捉中長線底部成形、季線轉強且短線展現爆發力的 V 轉契機。
  - 雙軌判定機制：提供兩種不同切入視角的觸發條件（【條件一】為穩健築底與短多排列，
    【條件二】為強勢突破與季線黃金交叉）。
  - 風控防禦：嚴格控管年線與季線斜率，並條件一引入年線未來 20 日高扣抵檢視，拒絕空頭深水區。

  ======================================================================
  二、 技術指標與共用基準計算 (Technical Indicators)
  ======================================================================
  - 移動平均線：MA5、MA10、MA20、MA60 (季線)、MA240 (年線)
  - 斜率與乖離計算：
    * 季線 20 日斜率 (`MA60_slope`)
    * 年線 20 日斜率 (`MA240_slope`)
    * 5日線 5 日斜率 (`MA5_slope`)

  ======================================================================
  三、 【條件一】穩健築底與短多排列條件 (Condition 1: Stable Base & Short Bullish)
  ======================================================================
  - 季線位置：季線必須在年線下方 (`MA60 < MA240`)。
  - 季線明確向上：季線 20 日斜率 `>= 0.001`。
  - 年線安全防禦：年線斜率 `>= -0.001`，且具備高扣抵防禦架構「未來 20 日無高扣抵壓力」
    （扣抵均價不大於現價 1.05 倍，避免年線遭拉彎下行）。
  - 短均結構：MA5、MA10、MA20 皆在季線下方，但彼此呈現多頭排列 (`MA5 > MA10 > MA20`)。

  ======================================================================
  四、 【條件二】強勢動能與季線突破條件 (Condition 2: Strong Breakout & Cross)
  ======================================================================
  - 基礎位置：季線在年線下方 (`MA60 < MA240`)。
  - 均線走平或走揚：年線與季線斜率皆 `>= -0.002`。
  - 突破表態：
    * 收盤價高於 5 日線 (`Close > MA5`)。
    * 5 日線向上突破季線（今日 `MA5 > MA60` 且昨日 `MA5 <= MA60`）。
    * 5 日線具備強勢斜率 (`> 0.005`) 且領先 10/20 日線 (`MA5 > MA10` 且 `MA5 > MA20`)。

  ======================================================================
  五、 綜合判定與輸出分流 (Classification & Output)
  ======================================================================
  - 觸發成功 (`is_hit = True`)：滿足【條件一】或【條件二】其中之一。
  - 狀態標註 (`status`)：明確標示符合單一條件或雙重條件，提供詳細日誌。
  - 輸出字典 (`info`)：包含收盤價、5日線、停損比例、季線與年線數值、
    各均線斜率、建議停損參考價（過去 20 日最低價）及策略狀態。
  ======================================================================
  """

  #修改自st_bottom_v_turn_2026073001, 增加判斷大盤收盤在相對於年線的位置
  
  print(f"\n 執行st_u_bottom, 目前是否在年線上 {market_above_ma240}%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")
  
  # 🌟 核心阻擋：若大盤在年線之下，右側突破策略直接不予觸發
  if not market_above_ma240:
    return False, {}
    
  #條件一已升級：限制季線必須向上，並加入未來 20 日年線高扣抵防禦, 從st_bottom_v_turn_2026072701退回此版"""
  if df_single.empty or len(df_single) < 280:
    return False, {}

  df_single = df_single.copy()

  # 計算各天期移動平均線
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA10'] = df_single['close'].rolling(10).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()  # 季線
  df_single['MA240'] = df_single['close'].rolling(240).mean()  # 年線

  # 計算均線 20 日斜率
  df_single['MA60_slope'] = (
      df_single['MA60'] - df_single['MA60'].shift(20)
  ) / df_single['MA60'].shift(20)
  df_single['MA240_slope'] = (
      df_single['MA240'] - df_single['MA240'].shift(20)
  ) / df_single['MA240'].shift(20)

  # 計算 5 日線 5 日斜率
  df_single['MA5_slope'] = (
      df_single['MA5'] - df_single['MA5'].shift(5)
  ) / df_single['MA5'].shift(5)

  today = df_single.iloc[-1]
  prev = df_single.iloc[-2]

  # 防禦性檢查
  if pd.isna([today['MA60'], today['MA240'], today['MA5']]).any():
    return False, {}

  close = today['close']
  ma5 = today['MA5']
  ma10 = today['MA10']
  ma20 = today['MA20']
  ma60 = today['MA60']
  ma240 = today['MA240']
  ma60_slope = today['MA60_slope']
  ma240_slope = today['MA240_slope']
  ma5_slope = today['MA5_slope']

  # ==================== 【條件一：嚴格優化版】 ====================
  # 1. 季線在年線下方
  c1_ma60_below_240 = ma60 < ma240

  # 2. 限制季線必須明確向上（斜率 >= 0.001）
  c1_ma60_rising = ma60_slope >= 0.001

  # 3. 年線斜率維持安全（>= -0.001），且檢查未來 20 日高扣抵值
  # 未來 20 日即將移出的歷史價格區間為 240 天前至 220 天前
  if len(df_single) >= 240:
    exiting_mean = df_single['close'].iloc[-240:-220].mean()
    # 若過去扣抵價平均顯著高於現價（超過 1.05 倍），代表未來 20 天面臨高扣抵，年線易受壓下彎
    c1_no_high_subtraction = exiting_mean <= (close * 1.05)
  else:
    c1_no_high_subtraction = True

  c1_ma240_safe = (ma240_slope >= -0.001) and c1_no_high_subtraction

  # 4. 5日、10日、20日亦在季線下方
  c1_short_below_60 = (ma5 < ma60) and (ma10 < ma60) and (ma20 < ma60)

  # 5. 且 5日、10日、20日形成多頭排列 (MA5 > MA10 > MA20)
  c1_short_bullish = (ma5 > ma10) and (ma10 > ma20)

  cond_1 = (
      c1_ma60_below_240
      and c1_ma60_rising
      and c1_ma240_safe
      and c1_short_below_60
      and c1_short_bullish
  )

  # ==================== 【條件二】（維持原強勢突破架構） ====================
  c2_ma60_below_240 = ma60 < ma240
  c2_ma240_flat_up = ma240_slope >= -0.002
  c2_ma60_flat_up = ma60_slope >= -0.002
  c2_close_gt_ma5 = close > ma5
  c2_ma5_cross = (ma5 > ma60) and (prev['MA5'] <= prev['MA60'])
  c2_ma5_slope = ma5_slope > 0.005
  c2_ma5_gt_10_20 = (ma5 > ma10) and (ma5 > ma20)

  cond_2 = (
      c2_ma60_below_240
      and c2_ma240_flat_up
      and c2_ma60_flat_up
      and c2_close_gt_ma5
      and c2_ma5_cross
      and c2_ma5_slope
      and c2_ma5_gt_10_20
  )

  # ==================== 【綜合判定與狀態標註】 ====================
  is_hit = cond_1 or cond_2

  if cond_1 and cond_2:
    status = '季線下同時符合短多排列與5日線突破'
  elif cond_1:
    status = (
        '季線明確向上,年線無高扣抵,5/10/20季線下短多排列'
    )
  elif cond_2:
    status = (
        '季線在年線下、年季線皆走平或走揚,5日線強勢突破季線且高於10/20日'
    )
  else:
    status = '未觸發訊號'

  # 計算近期停損參考價（過去 20 天最低價）
  recent_low = df_single['close'].iloc[-20:].min()
  #stop_loss = 0.2
  info = {
      '收盤': close,
      '策略狀態': status,
      '停損價': recent_low,
      '5日線': round(ma5, 2),
      '季線(60)': round(ma60, 2),
      '年線(240)': round(ma240, 2),
      '5日線5日斜率': f'{round(ma5_slope * 100, 2)}%',
      '季線20日斜率': f'{round(ma60_slope * 100, 2)}%',
      '年線20日斜率': f'{round(ma240_slope * 100, 2)}%',
  }

  return is_hit, info

def st_bottom_v_turn_2026073102(df_single, market_above_ma240=True):
  """V轉選股

  【條件一】為穩健築底與短多排列，【條件二】為強勢突破與季線黃金交叉

  修改自st_bottom_v_turn, 增加前五天內有跳空與量增的判斷, 暫時關閉大盤年線判斷 ---> 失敗, 沒有任何資料有判斷出5日內量縮與跳空, 無效退回原版
  ======================================================================
  一、 策略核心邏輯與設計精神 (Strategy Overview)
  ======================================================================
  - 核心目標：捕捉中長線底部成形、季線轉強且短線展現爆發力的 V 轉契機。
  - 雙軌判定機制：提供兩種不同切入視角的觸發條件（【條件一】為穩健築底與短多排列，
    【條件二】為強勢突破與季線黃金交叉）。
  - 風控防禦：嚴格控管年線與季線斜率，並條件一引入年線未來 20 日高扣抵檢視，拒絕空頭深水區。

  ======================================================================
  二、 技術指標與共用基準計算 (Technical Indicators)
  ======================================================================
  - 移動平均線：MA5、MA10、MA20、MA60 (季線)、MA240 (年線)
  - 斜率與乖離計算：
    * 季線 20 日斜率 (`MA60_slope`)
    * 年線 20 日斜率 (`MA240_slope`)
    * 5日線 5 日斜率 (`MA5_slope`)

  ======================================================================
  三、 【條件一】穩健築底與短多排列條件 (Condition 1: Stable Base & Short Bullish)
  ======================================================================
  - 季線位置：季線必須在年線下方 (`MA60 < MA240`)。
  - 季線明確向上：季線 20 日斜率 `>= 0.001`。
  - 年線安全防禦：年線斜率 `>= -0.001`，且具備高扣抵防禦架構「未來 20 日無高扣抵壓力」
    （扣抵均價不大於現價 1.05 倍，避免年線遭拉彎下行）。
  - 短均結構：MA5、MA10、MA20 皆在季線下方，但彼此呈現多頭排列 (`MA5 > MA10 > MA20`)。

  ======================================================================
  四、 【條件二】強勢動能與季線突破條件 (Condition 2: Strong Breakout & Cross)
  ======================================================================
  - 基礎位置：季線在年線下方 (`MA60 < MA240`)。
  - 均線走平或走揚：年線與季線斜率皆 `>= -0.002`。
  - 突破表態：
    * 收盤價高於 5 日線 (`Close > MA5`)。
    * 5 日線向上突破季線（今日 `MA5 > MA60` 且昨日 `MA5 <= MA60`）。
    * 5 日線具備強勢斜率 (`> 0.005`) 且領先 10/20 日線 (`MA5 > MA10` 且 `MA5 > MA20`)。

  ======================================================================
  五、 綜合判定與輸出分流 (Classification & Output)
  ======================================================================
  - 觸發成功 (`is_hit = True`)：滿足【條件一】或【條件二】其中之一。
  - 狀態標註 (`status`)：明確標示符合單一條件或雙重條件，並附帶量能與跳空狀態。
  - 輸出字典 (`info`)：包含收盤價、5日線、停損比例、季線與年線數值、
    各均線斜率、建議停損參考價、策略狀態、是否有跳空與是否有量增。
  ======================================================================
  """

  #print(f"\n 執行st_u_bottom, 目前是否在年線上market_above_ma240}%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")

  # 🌟 核心阻擋：若大盤在年線之下，右側突破策略直接不予觸發
  #if not market_above_ma240:  
    #return False, {}

  if df_single.empty or len(df_single) < 280:
    return False, {}

  df_single = df_single.copy()

  # 計算各天期移動平均線
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA10'] = df_single['close'].rolling(10).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()  # 季線
  df_single['MA240'] = df_single['close'].rolling(240).mean()  # 年線

  # 成交量 20 日均量
  if 'volume' in df_single.columns:
    df_single['VOL_MA20'] = df_single['volume'].rolling(20).mean()

  # 計算均線 20 日斜率
  df_single['MA60_slope'] = (
      df_single['MA60'] - df_single['MA60'].shift(20)
  ) / df_single['MA60'].shift(20)
  df_single['MA240_slope'] = (
      df_single['MA240'] - df_single['MA240'].shift(20)
  ) / df_single['MA240'].shift(20)

  # 計算 5 日線 5 日斜率
  df_single['MA5_slope'] = (
      df_single['MA5'] - df_single['MA5'].shift(5)
  ) / df_single['MA5'].shift(5)

  today = df_single.iloc[-1]
  prev = df_single.iloc[-2]

  # 防禦性檢查
  if pd.isna([today['MA60'], today['MA240'], today['MA5']]).any():
    return False, {}

  close = today['close']
  ma5 = today['MA5']
  ma10 = today['MA10']
  ma20 = today['MA20']
  ma60 = today['MA60']
  ma240 = today['MA240']
  ma60_slope = today['MA60_slope']
  ma240_slope = today['MA240_slope']
  ma5_slope = today['MA5_slope']

  # ==================== 【新加入：量能與跳空判斷】 ====================
  has_gap = False
  has_volume_surge = False

  if (
      len(df_single) >= 5
      and 'high' in df_single.columns
      and 'low' in df_single.columns
      and 'volume' in df_single.columns
  ):
    recent_5 = df_single.iloc[-5:]
    # 檢查過去 5 天內是否有向上跳空 (當日最低價 > 昨日最高價)
    for i in range(1, len(recent_5)):
      curr_row = recent_5.iloc[i]
      prev_row = recent_5.iloc[i - 1]
      if curr_row['low'] > prev_row['high']:
        has_gap = True
        break

    # 檢查過去 5 天內是否有任一日爆大量 (成交量 >= 2 倍 20日均量)
    for _, row in recent_5.iterrows():
      vol_ma = row.get('VOL_MA20', 0)
      if pd.notna(vol_ma) and vol_ma > 0:
        if row['volume'] >= 2.0 * vol_ma:
          has_volume_surge = True
          break

  # ==================== 【條件一：嚴格優化版】 ====================
  c1_ma60_below_240 = ma60 < ma240
  c1_ma60_rising = ma60_slope >= 0.001

  if len(df_single) >= 240:
    exiting_mean = df_single['close'].iloc[-240:-220].mean()
    c1_no_high_subtraction = exiting_mean <= (close * 1.05)
  else:
    c1_no_high_subtraction = True

  c1_ma240_safe = (ma240_slope >= -0.001) and c1_no_high_subtraction
  c1_short_below_60 = (ma5 < ma60) and (ma10 < ma60) and (ma20 < ma60)
  c1_short_bullish = (ma5 > ma10) and (ma10 > ma20)

  cond_1 = (
      c1_ma60_below_240
      and c1_ma60_rising
      and c1_ma240_safe
      and c1_short_below_60
      and c1_short_bullish
  )

  # ==================== 【條件二】 ====================
  c2_ma60_below_240 = ma60 < ma240
  c2_ma240_flat_up = ma240_slope >= -0.002
  c2_ma60_flat_up = ma60_slope >= -0.002
  c2_close_gt_ma5 = close > ma5
  c2_ma5_cross = (ma5 > ma60) and (prev['MA5'] <= prev['MA60'])
  c2_ma5_slope = ma5_slope > 0.005
  c2_ma5_gt_10_20 = (ma5 > ma10) and (ma5 > ma20)

  cond_2 = (
      c2_ma60_below_240
      and c2_ma240_flat_up
      and c2_ma60_flat_up
      and c2_close_gt_ma5
      and c2_ma5_cross
      and c2_ma5_slope
      and c2_ma5_gt_10_20
  )

  # ==================== 【綜合判定與狀態標註】 ====================
  is_hit = cond_1 or cond_2

  if cond_1 and cond_2:
    base_status = '季線下同時符合短多排列與5日線突破'
  elif cond_1:
    base_status = '季線明確向上,年線無高扣抵,5/10/20季線下短多排列'
  elif cond_2:
    base_status = (
        '季線在年線下、年季線皆走平或走揚,5日線強勢突破季線且高於10/20日'
    )
  else:
    base_status = '未觸發訊號'

  # 附加量能與跳空標註
  extra_tags = []
  if has_gap:
    extra_tags.append('有跳空')
  if has_volume_surge:
    extra_tags.append('有量增')

  status = base_status
  if extra_tags:
    status += ' [' + ', '.join(extra_tags) + ']'

  recent_low = df_single['close'].iloc[-20:].min()
  info = {
      '收盤': close,
      '策略狀態': status,
      '停損價': recent_low,
      '5日線': round(ma5, 2),
      '季線(60)': round(ma60, 2),
      '年線(240)': round(ma240, 2),
      '5日線5日斜率': f'{round(ma5_slope * 100, 2)}%',
      '季線20日斜率': f'{round(ma60_slope * 100, 2)}%',
      '年線20日斜率': f'{round(ma240_slope * 100, 2)}%',
      '有跳空': '是' if has_gap else '否',
      '有量增': '是' if has_volume_surge else '否',
  }

  return is_hit, info


def st_bottom_v_turn_2026073001(df_single):
  """V轉選股
  【條件一】為穩健築底與短多排列，【條件二】為強勢突破與季線黃金交叉 

  ======================================================================
  一、 策略核心邏輯與設計精神 (Strategy Overview)
  ======================================================================
  - 核心目標：捕捉中長線底部成形、季線轉強且短線展現爆發力的 V 轉契機。
  - 雙軌判定機制：提供兩種不同切入視角的觸發條件（【條件一】為穩健築底與短多排列，
    【條件二】為強勢突破與季線黃金交叉）。
  - 風控防禦：嚴格控管年線與季線斜率，並條件一引入年線未來 20 日高扣抵檢視，拒絕空頭深水區。

  ======================================================================
  二、 技術指標與共用基準計算 (Technical Indicators)
  ======================================================================
  - 移動平均線：MA5、MA10、MA20、MA60 (季線)、MA240 (年線)
  - 斜率與乖離計算：
    * 季線 20 日斜率 (`MA60_slope`)
    * 年線 20 日斜率 (`MA240_slope`)
    * 5日線 5 日斜率 (`MA5_slope`)

  ======================================================================
  三、 【條件一】穩健築底與短多排列條件 (Condition 1: Stable Base & Short Bullish)
  ======================================================================
  - 季線位置：季線必須在年線下方 (`MA60 < MA240`)。
  - 季線明確向上：季線 20 日斜率 `>= 0.001`。
  - 年線安全防禦：年線斜率 `>= -0.001`，且具備高扣抵防禦架構「未來 20 日無高扣抵壓力」
    （扣抵均價不大於現價 1.05 倍，避免年線遭拉彎下行）。
  - 短均結構：MA5、MA10、MA20 皆在季線下方，但彼此呈現多頭排列 (`MA5 > MA10 > MA20`)。

  ======================================================================
  四、 【條件二】強勢動能與季線突破條件 (Condition 2: Strong Breakout & Cross)
  ======================================================================
  - 基礎位置：季線在年線下方 (`MA60 < MA240`)。
  - 均線走平或走揚：年線與季線斜率皆 `>= -0.002`。
  - 突破表態：
    * 收盤價高於 5 日線 (`Close > MA5`)。
    * 5 日線向上突破季線（今日 `MA5 > MA60` 且昨日 `MA5 <= MA60`）。
    * 5 日線具備強勢斜率 (`> 0.005`) 且領先 10/20 日線 (`MA5 > MA10` 且 `MA5 > MA20`)。

  ======================================================================
  五、 綜合判定與輸出分流 (Classification & Output)
  ======================================================================
  - 觸發成功 (`is_hit = True`)：滿足【條件一】或【條件二】其中之一。
  - 狀態標註 (`status`)：明確標示符合單一條件或雙重條件，提供詳細日誌。
  - 輸出字典 (`info`)：包含收盤價、5日線、停損比例、季線與年線數值、
    各均線斜率、建議停損參考價（過去 20 日最低價）及策略狀態。
  ======================================================================
  """
  
  #條件一已升級：限制季線必須向上，並加入未來 20 日年線高扣抵防禦, 從st_bottom_v_turn_2026072701退回此版"""
  if df_single.empty or len(df_single) < 280:
    return False, {}

  df_single = df_single.copy()

  # 計算各天期移動平均線
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA10'] = df_single['close'].rolling(10).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()  # 季線
  df_single['MA240'] = df_single['close'].rolling(240).mean()  # 年線

  # 計算均線 20 日斜率
  df_single['MA60_slope'] = (
      df_single['MA60'] - df_single['MA60'].shift(20)
  ) / df_single['MA60'].shift(20)
  df_single['MA240_slope'] = (
      df_single['MA240'] - df_single['MA240'].shift(20)
  ) / df_single['MA240'].shift(20)

  # 計算 5 日線 5 日斜率
  df_single['MA5_slope'] = (
      df_single['MA5'] - df_single['MA5'].shift(5)
  ) / df_single['MA5'].shift(5)

  today = df_single.iloc[-1]
  prev = df_single.iloc[-2]

  # 防禦性檢查
  if pd.isna([today['MA60'], today['MA240'], today['MA5']]).any():
    return False, {}

  close = today['close']
  ma5 = today['MA5']
  ma10 = today['MA10']
  ma20 = today['MA20']
  ma60 = today['MA60']
  ma240 = today['MA240']
  ma60_slope = today['MA60_slope']
  ma240_slope = today['MA240_slope']
  ma5_slope = today['MA5_slope']

  # ==================== 【條件一：嚴格優化版】 ====================
  # 1. 季線在年線下方
  c1_ma60_below_240 = ma60 < ma240

  # 2. 限制季線必須明確向上（斜率 >= 0.001）
  c1_ma60_rising = ma60_slope >= 0.001

  # 3. 年線斜率維持安全（>= -0.001），且檢查未來 20 日高扣抵值
  # 未來 20 日即將移出的歷史價格區間為 240 天前至 220 天前
  if len(df_single) >= 240:
    exiting_mean = df_single['close'].iloc[-240:-220].mean()
    # 若過去扣抵價平均顯著高於現價（超過 1.05 倍），代表未來 20 天面臨高扣抵，年線易受壓下彎
    c1_no_high_subtraction = exiting_mean <= (close * 1.05)
  else:
    c1_no_high_subtraction = True

  c1_ma240_safe = (ma240_slope >= -0.001) and c1_no_high_subtraction

  # 4. 5日、10日、20日亦在季線下方
  c1_short_below_60 = (ma5 < ma60) and (ma10 < ma60) and (ma20 < ma60)

  # 5. 且 5日、10日、20日形成多頭排列 (MA5 > MA10 > MA20)
  c1_short_bullish = (ma5 > ma10) and (ma10 > ma20)

  cond_1 = (
      c1_ma60_below_240
      and c1_ma60_rising
      and c1_ma240_safe
      and c1_short_below_60
      and c1_short_bullish
  )

  # ==================== 【條件二】（維持原強勢突破架構） ====================
  c2_ma60_below_240 = ma60 < ma240
  c2_ma240_flat_up = ma240_slope >= -0.002
  c2_ma60_flat_up = ma60_slope >= -0.002
  c2_close_gt_ma5 = close > ma5
  c2_ma5_cross = (ma5 > ma60) and (prev['MA5'] <= prev['MA60'])
  c2_ma5_slope = ma5_slope > 0.005
  c2_ma5_gt_10_20 = (ma5 > ma10) and (ma5 > ma20)

  cond_2 = (
      c2_ma60_below_240
      and c2_ma240_flat_up
      and c2_ma60_flat_up
      and c2_close_gt_ma5
      and c2_ma5_cross
      and c2_ma5_slope
      and c2_ma5_gt_10_20
  )

  # ==================== 【綜合判定與狀態標註】 ====================
  is_hit = cond_1 or cond_2

  if cond_1 and cond_2:
    status = '季線下同時符合短多排列與5日線突破'
  elif cond_1:
    status = (
        '季線明確向上,年線無高扣抵,5/10/20季線下短多排列'
    )
  elif cond_2:
    status = (
        '季線在年線下、年季線皆走平或走揚,5日線強勢突破季線且高於10/20日'
    )
  else:
    status = '未觸發訊號'

  # 計算近期停損參考價（過去 20 天最低價）
  recent_low = df_single['close'].iloc[-20:].min()
  #stop_loss = 0.2
  info = {
      '收盤': close,
      '策略狀態': status,
      '停損價': recent_low,
      '5日線': round(ma5, 2),
      '季線(60)': round(ma60, 2),
      '年線(240)': round(ma240, 2),
      '5日線5日斜率': f'{round(ma5_slope * 100, 2)}%',
      '季線20日斜率': f'{round(ma60_slope * 100, 2)}%',
      '年線20日斜率': f'{round(ma240_slope * 100, 2)}%',
  }

  return is_hit, info


def st_bottom_v_turn_2026072701(df_single):
  """***V 轉選股策略（條件一已升級：限制季線必須向上、加入年線與未來 20 日季線高扣抵防禦）***增加季線高扣抵會導致篩選掉高報酬的股票, 故放棄,"""
  #對應回測資料為yf_test_st_bottom_v_turn_range_2015-01-01_to_2025-09-30_20260726_2313
  # yf_test_st_bottom_v_turn_range_2021-01-01_to_2025-09-30_20260726_2126
  if df_single.empty or len(df_single) < 280:
    return False, {}

  df_single = df_single.copy()

  # 計算各天期移動平均線
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA10'] = df_single['close'].rolling(10).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()  # 季線
  df_single['MA240'] = df_single['close'].rolling(240).mean()  # 年線

  # 計算均線 20 日斜率
  df_single['MA60_slope'] = (
      df_single['MA60'] - df_single['MA60'].shift(20)
  ) / df_single['MA60'].shift(20)
  df_single['MA240_slope'] = (
      df_single['MA240'] - df_single['MA240'].shift(20)
  ) / df_single['MA240'].shift(20)

  # 計算 5 日線 5 日斜率
  df_single['MA5_slope'] = (
      df_single['MA5'] - df_single['MA5'].shift(5)
  ) / df_single['MA5'].shift(5)

  today = df_single.iloc[-1]
  prev = df_single.iloc[-2]

  # 防禦性檢查
  if pd.isna([today['MA60'], today['MA240'], today['MA5']]).any():
    return False, {}

  close = today['close']
  ma5 = today['MA5']
  ma10 = today['MA10']
  ma20 = today['MA20']
  ma60 = today['MA60']
  ma240 = today['MA240']
  ma60_slope = today['MA60_slope']
  ma240_slope = today['MA240_slope']
  ma5_slope = today['MA5_slope']

  # ==================== 【條件一：嚴格優化版（含季線/年線雙重扣抵防禦）】 ====================
  # 1. 季線在年線下方
  c1_ma60_below_240 = ma60 < ma240

  # 2. 限制季線必須明確向上（斜率 >= 0.001）
  c1_ma60_rising = ma60_slope >= 0.001

  # 3. 季線扣抵防禦：檢查未來 20 日（即將移出的歷史價格 60 天前至 40 天前）
  if len(df_single) >= 60:
    exiting_mean_ma60 = df_single['close'].iloc[-60:-40].mean()
    # 若過去季線扣抵價平均顯著高於現價（超過 1.05 倍），代表未來面臨高扣抵，季線易受壓下彎
    c1_ma60_no_high_subtraction = exiting_mean_ma60 <= (close * 1.05)
  else:
    c1_ma60_no_high_subtraction = True

  c1_ma60_safe = c1_ma60_rising and c1_ma60_no_high_subtraction

  # 4. 年線斜率維持安全（>= -0.001），且檢查未來 20 日高扣抵值 (240 天前至 220 天前)
  if len(df_single) >= 240:
    exiting_mean_ma240 = df_single['close'].iloc[-240:-220].mean()
    c1_no_high_subtraction = exiting_mean_ma240 <= (close * 1.05)
  else:
    c1_no_high_subtraction = True

  c1_ma240_safe = (ma240_slope >= -0.001) and c1_no_high_subtraction

  # 5. 5日、10日、20日亦在季線下方
  c1_short_below_60 = (ma5 < ma60) and (ma10 < ma60) and (ma20 < ma60)

  # 6. 且 5日、10日、20日形成多頭排列 (MA5 > MA10 > MA20)
  c1_short_bullish = (ma5 > ma10) and (ma10 > ma20)

  cond_1 = (
      c1_ma60_below_240
      and c1_ma60_safe
      and c1_ma240_safe
      and c1_short_below_60
      and c1_short_bullish
  )

  # ==================== 【條件二】（維持原強勢突破架構，不加季線扣抵防禦） ====================
  c2_ma60_below_240 = ma60 < ma240
  c2_ma240_flat_up = ma240_slope >= -0.002
  c2_ma60_flat_up = ma60_slope >= -0.002
  c2_close_gt_ma5 = close > ma5
  c2_ma5_cross = (ma5 > ma60) and (prev['MA5'] <= prev['MA60'])
  c2_ma5_slope = ma5_slope > 0.005
  c2_ma5_gt_10_20 = (ma5 > ma10) and (ma5 > ma20)

  cond_2 = (
      c2_ma60_below_240
      and c2_ma240_flat_up
      and c2_ma60_flat_up
      and c2_close_gt_ma5
      and c2_ma5_cross
      and c2_ma5_slope
      and c2_ma5_gt_10_20
  )

  # ==================== 【綜合判定與狀態標註】 ====================
  is_hit = cond_1 or cond_2

  if cond_1 and cond_2:
    status = '[V轉策略] 同時符合【條件一】與【條件二】'
  elif cond_1:
    status = (
        '[V轉策略] 符合【條件一】(季線在年線下、季線明確向上且無高扣抵疑慮、'
        '年線無高扣抵疑慮、5/10/20在季線下且短多排列)'
    )
  elif cond_2:
    status = (
        '[V轉策略] 符合【條件二】(季線在年線下、年季線皆走平或走揚、'
        '5日線強勢突破季線且高於10/20日)'
    )
  else:
    status = '未觸發訊號'

  # 計算近期停損參考價（過去 20 天最低價）
  recent_low = df_single['close'].iloc[-20:].min()

  info = {
      '收盤': close,
      '5日線': round(ma5, 2),
      '季線(MA60)': round(ma60, 2),
      '年線(MA240)': round(ma240, 2),
      '季線20日斜率': f'{round(ma60_slope * 100, 2)}%',
      '年線20日斜率': f'{round(ma240_slope * 100, 2)}%',
      '5日線5日斜率': f'{round(ma5_slope * 100, 2)}%',
      '建議停損參考價': recent_low,
      '策略狀態': status,
  }

  return is_hit, info

def st_bottom_v_turn_2026072602(df_single):
 
  """***V 轉選股策略（條件一/二獨立觸發，並依策略屬性自動套用對應的量能檢核狀態）, 增加量能判斷***"""
  if df_single.empty or len(df_single) < 280:
    return False, {}

  df_single = df_single.copy()

  # 計算各天期移動平均線
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA10'] = df_single['close'].rolling(10).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()  # 季線
  df_single['MA240'] = df_single['close'].rolling(240).mean()  # 年線

  # 計算成交量相關指標 (MA20_Vol 與 5日均量 MA5_Vol)
  vol_col = 'volume' if 'volume' in df_single.columns else 'Volume'
  if vol_col in df_single.columns:
    df_single['Vol_MA20'] = df_single[vol_col].rolling(20).mean()
    df_single['Vol_MA5'] = df_single[vol_col].rolling(5).mean()
  else:
    df_single['Vol_MA20'] = 0
    df_single['Vol_MA5'] = 0

  # 計算均線 20 日斜率
  df_single['MA60_slope'] = (
      df_single['MA60'] - df_single['MA60'].shift(20)
  ) / df_single['MA60'].shift(20)
  df_single['MA240_slope'] = (
      df_single['MA240'] - df_single['MA240'].shift(20)
  ) / df_single['MA240'].shift(20)

  # 計算 5 日線 5 日斜率
  df_single['MA5_slope'] = (
      df_single['MA5'] - df_single['MA5'].shift(5)
  ) / df_single['MA5'].shift(5)

  # 計算 5 日均量斜率 (判斷 5日均量是否向上：今日 MA5_Vol > 昨天 MA5_Vol)
  df_single['Vol_MA5_slope'] = df_single['Vol_MA5'] - df_single['Vol_MA5'].shift(
      1
  )

  today = df_single.iloc[-1]
  prev = df_single.iloc[-2]

  # 防禦性檢查
  if pd.isna([today['MA60'], today['MA240'], today['MA5']]).any():
    return False, {}

  close = today['close']
  ma5 = today['MA5']
  ma10 = today['MA10']
  ma20 = today['MA20']
  ma60 = today['MA60']
  ma240 = today['MA240']
  ma60_slope = today['MA60_slope']
  ma240_slope = today['MA240_slope']
  ma5_slope = today['MA5_slope']

  # ==================== 【條件一】 ====================
  c1_ma60_below_240 = ma60 < ma240
  c1_at_least_one_rising = (ma60_slope >= -0.001) or (ma240_slope >= -0.001)
  c1_short_below_60 = (ma5 < ma60) and (ma10 < ma60) and (ma20 < ma60)
  c1_short_bullish = (ma5 > ma10) and (ma10 > ma20)

  cond_1 = (
      c1_ma60_below_240
      and c1_at_least_one_rising
      and c1_short_below_60
      and c1_short_bullish
  )

  # ==================== 【條件二】 ====================
  c2_ma60_below_240 = ma60 < ma240
  c2_ma240_flat_up = ma240_slope >= -0.002
  c2_ma60_flat_up = ma60_slope >= -0.002
  c2_close_gt_ma5 = close > ma5
  c2_ma5_cross = (ma5 > ma60) and (prev['MA5'] <= prev['MA60'])
  c2_ma5_slope = ma5_slope > 0.005
  c2_ma5_gt_10_20 = (ma5 > ma10) and (ma5 > ma20)

  cond_2 = (
      c2_ma60_below_240
      and c2_ma240_flat_up
      and c2_ma60_flat_up
      and c2_close_gt_ma5
      and c2_ma5_cross
      and c2_ma5_slope
      and c2_ma5_gt_10_20
  )

  is_hit = cond_1 or cond_2

  # ==================== 【放寬後的量能狀態檢核】 ====================
  vol_status = '未觸發訊號'

  if vol_col in df_single.columns and len(df_single) >= 5:
    today_vol = today[vol_col]
    today_vol_ma20 = today['Vol_MA20']

    if pd.notna(today_vol_ma20) and today_vol_ma20 > 0:
      if cond_2 and not cond_1:
        # 【條件二：強勢突破放寬版】當日成交量 >= 20日均量 × 1.2
        if (today_vol / today_vol_ma20) >= 1.2:
          vol_status = '[條件二] 符合(成交量放大突破)'
        else:
          vol_status = '[條件二] 未符合(量能未明顯放大)'

      elif cond_1 and not cond_2:
        # 【條件一：長多回檔放寬版】當天成交量大於 20 日均量，或大於前一日成交量
        prev_vol = prev[vol_col]
        if (today_vol >= today_vol_ma20) or (today_vol > prev_vol):
          vol_status = '[條件一] 符合(回檔後量能回溫)'
        else:
          vol_status = '[條件一] 未符合(量能偏低)'

      elif cond_1 and cond_2:
        if (today_vol / today_vol_ma20) >= 1.2:
          vol_status = '[綜合] 符合(雙條件且量能放大)'
        else:
          vol_status = '[綜合] 未符合(量能不足)'
      else:
        vol_status = '未觸發訊號'

    elif cond_1 and not cond_2:
      # 【條件一：長多回檔邏輯】前 5 天內曾出現量縮回測，且觸發當天帶量大於 5 日均量
      recent_5d = df_single.iloc[-5:]  # 含今日共 5 天
      has_shrink = False
      for _, row_v in recent_5d.iloc[:-1].iterrows():  # 檢查前 4 天是否有量縮
        v = row_v[vol_col]
        v_ma20 = row_v['Vol_MA20']
        if pd.notna(v_ma20) and v_ma20 > 0:
          if (v / v_ma20) < 0.8:  # 量縮定義：小於 20 日均量 0.8 倍
            has_shrink = True
            break

      today_v = today[vol_col]
      today_v_ma5 = today['Vol_MA5']
      is_today_gt_vma5 = (
          pd.notna(today_v_ma5)
          and today_v_ma5 > 0
          and today_v > today_v_ma5
      )

      cond_vol_1 = has_shrink and is_today_gt_vma5
      vol_status = (
          '[條件一] 符合(量縮回測後帶量回流)'
          if cond_vol_1
          else '[條件一] 未符合(未見明顯量縮或觸發當天無量)'
      )

    elif cond_1 and cond_2:
      vol_status = '[綜合] 同時符合條件一與條件二(雙軌檢核中)'
    else:
      vol_status = '未觸發訊號'

  # ==================== 【綜合判定與狀態標註】 ====================
  if cond_1 and cond_2:
    status = '[V轉策略] 同時符合【條件一】與【條件二】'
  elif cond_1:
    status = (
        '[V轉策略] 符合【條件一】(季線在年線下、長線至少一條走揚、'
        '5/10/20在季線下且短多排列)'
    )
  elif cond_2:
    status = (
        '[V轉策略] 符合【條件二】(季線在年線下、年季線皆走平或走揚、'
        '5日線強勢突破季線且高於10/20日)'
    )
  else:
    status = '未觸發訊號'

  # 計算近期停損參考價（過去 20 天最低價）
  recent_low = df_single['close'].iloc[-20:].min()

  info = {
      '收盤': close,
      '5日線': round(ma5, 2),
      '季線(MA60)': round(ma60, 2),
      '年線(MA240)': round(ma240, 2),
      '季線20日斜率': f'{round(ma60_slope * 100, 2)}%',
      '年線20日斜率': f'{round(ma240_slope * 100, 2)}%',
      '5日線5日斜率': f'{round(ma5_slope * 100, 2)}%',
      '建議停損參考價': recent_low,
      '量能狀態': vol_status,  # 依條件一/二自動切換對應的量能檢核結果
      '策略狀態': status,
  }

  return is_hit, info


def st_bottom_v_turn_20260726(df_single):
    """
    ***底部篩選 - 左側超跌 V 轉模式 (優化版 + 防禦過熱機制)***
    
    新增功能：
    - 導入 MAX_SLOPE_LIMIT (1.2%)，主動過濾掉已進入泡沫或過熱修正階段的個股。
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 建立副本以避免修改到外部原始 DataFrame
    df_single = df_single.copy()
    
    # 計算技術指標
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    vol_ma5 = today['Vol_MA5']
    
    # 基底檢查：股價在年線下方
    is_below_ma240 = today['close'] < today['MA240']
    
    # 計算年線 20 日斜率
    ma240_20d_ago = df_single['MA240'].iloc[-21]
    ma_slope_20d = (today['MA240'] - ma240_20d_ago) / ma240_20d_ago if ma240_20d_ago > 0 else 0
    
    # 計算負乖離率
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']

    # 【核心防禦機制】：過濾斜率過熱股 (設定上限為 1.2%)
    MAX_SLOPE_LIMIT = 0.012 
    is_slope_healthy = ma_slope_20d <= MAX_SLOPE_LIMIT
    
    # 執行超跌檢查
    is_oversold_zone = -0.20 <= dist_ratio <= -0.10
    
    # 計算今日量比
    vol_ratio = today['Trading_Volume'] / vol_ma5 if vol_ma5 > 0 else 0
    is_huge_volume = vol_ratio >= 2.5
    
    # ==================== 【天量催化劑動態門檻】 ====================
    if is_huge_volume:
        slope_threshold = -0.01 
        status_tag = "[左側天量V轉]大多頭催化劑發動! 主力/庫藏股爆量硬拉"
    else:
        slope_threshold = -0.002
        status_tag = "[左側超跌]多頭拉回錯殺, 年線維持標準多頭慣性"
        
    is_v_turn_slope = ma_slope_20d > slope_threshold
    # ===============================================================
    
    # 【綜合判定】：新增 is_slope_healthy 檢查
    is_hit = is_below_ma240 and is_oversold_zone and is_v_turn_slope and is_slope_healthy
    
    # 狀態輸出邏輯：特別標註被過濾掉的過熱股
    if not is_slope_healthy and (is_below_ma240 and is_oversold_zone and is_v_turn_slope):
        status = f"[過濾]斜率過熱({round(ma_slope_20d * 100, 2)}%)"
    else:
        status = status_tag if is_hit else "未觸發訊號"
    
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線20日斜率": f"{round(ma_slope_20d * 100, 2)}%",
        "今日量比": f"{round(vol_ratio, 2)}x",
        "動態斜率門檻": f"{round(slope_threshold * 100, 2)}%",
        "策略狀態": status
    }
        
    return is_hit, info


def st_bottom_v_turn_071902(df_single):
    """
    ***底部篩選 - 左側超跌 V 轉模式 (優化版)***
    
    優化邏輯：
    1. 收窄超跌區間：將 -5%~-20% 調整為 -10%~-20%，過濾掉缺乏爆發力的弱勢股。
    2. 維持天量催化：保持 2.5x 爆量門檻，確保進場訊號具有主力護盤確認。
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 計算技術指標
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    vol_ma5 = today['Vol_MA5']
    
    # 基底檢查：股價在年線下方
    is_below_ma240 = today['close'] < today['MA240']
    
    # 計算年線 20 日斜率（百分比變動）
    ma240_20d_ago = df_single['MA240'].iloc[-21]
    ma_slope_20d = (today['MA240'] - ma240_20d_ago) / ma240_20d_ago if ma240_20d_ago > 0 else 0
    
    # 計算負乖離率
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']

    # 【優化重點 1】：收窄超跌定義，過濾掉修正幅度不足的股票 (只挑 -10% ~ -20%)
    is_oversold_zone = -0.20 <= dist_ratio <= -0.10
    
    # 計算今日量比
    vol_ratio = today['Trading_Volume'] / vol_ma5 if vol_ma5 > 0 else 0
    is_huge_volume = vol_ratio >= 2.5
    
    # ==================== 【天量催化劑動態門檻】 ====================
    if is_huge_volume:
        # 爆量時，放寬年線限制到 -1.0%，捕捉強力的暴力 V 轉
        slope_threshold = -0.01 
        status_tag = "[左側天量V轉]大多頭催化劑發動! 主力/庫藏股爆量硬拉"
    else:
        # 平常無量時，嚴格鎖死在 -0.2% 進行防禦，拒絕承接緩跌盤
        slope_threshold = -0.002
        status_tag = "[左側超跌]多頭拉回錯殺, 年線維持標準多頭慣性"
        
    is_v_turn_slope = ma_slope_20d > slope_threshold
    # ===============================================================
    
    # 綜合判定 (is_below_ma240 & is_oversold_zone & is_v_turn_slope)
    is_hit = is_below_ma240 and is_oversold_zone and is_v_turn_slope
    
    status = status_tag if is_hit else "未觸發訊號"
    
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線20日斜率": f"{round(ma_slope_20d * 100, 2)}%",
        "今日量比": f"{round(vol_ratio, 2)}x",
        "動態斜率門檻": f"{round(slope_threshold * 100, 2)}%",
        "策略狀態": status
    }

    #if is_hit : 
    #    print(f"st_bottom_v_turn is_hit:{is_hit} 收盤:{today['close']}") # 建議正式運作時註解掉 print
        
    return is_hit, info

def st_bottom_v_turn_071901(df_single):
    """
    ***底部篩選 - 左側超跌 V 轉模式 (含天量催化劑後門)***
    
    邏輯設計：
    1. 平常時期 (無量)：嚴格執行 -0.2% 斜率限制，確保長線多頭慣性完好。
    2. 天量時期 (爆量)：今日量比 >= 2.5x，代表多頭市場主力/庫藏股強力介入，
       破例啟動後門，放寬年線斜率限制至 -1.0%，用以捕捉群光 (-0.77%) 這類的暴力 V 轉股。
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 計算技術指標
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    vol_ma5 = today['Vol_MA5']
    
    # 基底檢查：股價在年線下方
    is_below_ma240 = today['close'] < today['MA240']
    
    # 計算年線 20 日斜率（百分比變動）
    ma240_20d_ago = df_single['MA240'].iloc[-21]
    ma_slope_20d = (today['MA240'] - ma240_20d_ago) / ma240_20d_ago if ma240_20d_ago > 0 else 0
    
    # 計算負乖離率
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']

     # 適用於台灣50, 乖離率在8%~15%間
    #is_oversold_zone = -0.15 <= dist_ratio <= -0.08
    
    #中型100必須等到跌破年線 12% 以上，中型股的融資停損潮才剛開始浮現；
    #跌到 20% 附近通常是斷頭潮高潮。這時配上年線斜率沒壞（> -0.2%），才是真正的「主力洗盤錯殺」。    
    is_oversold_zone = -0.20 <= dist_ratio <= -0.05
    
    # 計算今日量比
    vol_ratio = today['Trading_Volume'] / vol_ma5 if vol_ma5 > 0 else 0
    is_huge_volume = vol_ratio >= 2.5
    
    # ==================== 【天量催化劑動態門檻】 ====================
    if is_huge_volume:
        slope_threshold = -0.01  # 爆量時，放寬年線限制到 -1.0% (群光的 -0.77% 可安全過關)
        status_tag = "[左側天量V轉]大多頭催化劑發動! 主力/庫藏股爆量硬拉, 破例放寬年線限制"
    else:
        slope_threshold = -0.002  # 平常無量時，嚴格鎖死在 -0.2% 進行安全防禦
        status_tag = "[左側超跌]多頭拉回錯殺, 年線維持標準多頭慣性"
        
    is_v_turn_slope = ma_slope_20d > slope_threshold
    # ===============================================================
    
    # 綜合判定
    is_hit = is_below_ma240 and is_oversold_zone and is_v_turn_slope
    
    status = status_tag if is_hit else "未觸發訊號"
    
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線20日斜率": f"{round(ma_slope_20d * 100, 2)}%",
        "今日量比": f"{round(vol_ratio, 2)}x",
        "動態斜率門檻": f"{round(slope_threshold * 100, 2)}%",
        "策略狀態": status
    }

    print(f"st_bottom_v_turn is_hit:{is_hit} info:{info}")
    return is_hit, info

def st_bottom_consolidation(df_single):
    """
    ***底部篩選 - 左側橫盤沉澱模式 (含未來 20 日扣抵預測)***
    特徵：股價止跌橫盤，但年線因扣抵高價區而持續下彎。
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 計算技術指標
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    today = df_single.iloc[-1]
    
    # 基底檢查
    is_below_ma240 = today['close'] < today['MA240']
    
    # 當前年線 20 日斜率
    ma240_20d_ago = df_single['MA240'].iloc[-21]
    ma_slope_20d = (today['MA240'] - ma240_20d_ago) / ma240_20d_ago if ma240_20d_ago > 0 else 0
    
    # 條件 1：年線仍在下彎階段
    is_downward_slope = ma_slope_20d < -0.002
    
    # 條件 2：近 10 日價格實質止跌 (變異係數 < 1.5%)
    recent_10d = df_single['close'].iloc[-10:]
    price_cv = recent_10d.std() / recent_10d.mean() if recent_10d.mean() > 0 else 1
    is_price_stabilized = price_cv < 0.015 
    
    # 條件 3：維持中型股安全負乖離空間（確保股價夠便宜，且年線還沒完全壓到頭頂）
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
   
    # 適用於台灣50, 乖離率在5%~15%間
    # is_discounted = -0.15 <= dist_ratio <= -0.05

    # 適用中型100經歷過一段暴跌後，它現在在年線下方約 10% 到 15% 的空間開始橫盤。中型股如果只跌 5% 就橫盤，通常沉澱得不夠乾淨，上面解套賣壓還很重。
    is_discounted = -0.20 <= dist_ratio <= -0.08
    
    # ==================== 【核心升級：未來 20 日扣抵分析】 ====================
    # 接下來 20 天年線即將丟棄的一年前歷史價格
    future_deduct_series = df_single['close'].iloc[-240:-220]
    avg_deduct_price = future_deduct_series.mean()
    
    # 扣抵坡度：如果 < 0，代表未來的扣抵牆正在「往下墜落」，壓力將減輕
    deduct_slope = (future_deduct_series.iloc[-1] - future_deduct_series.iloc[0]) / future_deduct_series.iloc[0]
    
    # 判斷需要熬多久（時間矩陣）
    if today['close'] < avg_deduct_price * 0.85:
        time_to_wait = "(觀察)扣抵高價壁壘仍重, 預估至少仍需橫盤20天以上"
    elif deduct_slope < -0.05:
        time_to_wait = "(觀察)高價扣抵即將墜落, 年線即將減速, 隨時注意右側突破"
    else:
        time_to_wait = "(可買進)橫盤扣抵中, 靜待均線糾結"
    # =====================================================================
    
    is_hit = is_below_ma240 and is_downward_slope and is_price_stabilized and is_discounted
    status = f"[左側沉澱] 價格已止跌 | {time_to_wait}" if is_hit else "未觸發訊號"
    
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線20日斜率": f"{round(ma_slope_20d * 100, 2)}%",
        "近10日價格波動度": f"{round(price_cv * 100, 2)}%",
        "未來20日扣抵均價": f"{round(avg_deduct_price, 2)}元",
        "預估沉澱時間": time_to_wait,
        "策略狀態": status
    }

    print(f"st_bottom_consolidation is_hit:{is_hit} info:{info}")
    return is_hit, info

def st_bottom_breakout(df_single):
    """
    ***底部篩選 - 右側打底壓縮突破模式 (含扣抵重力釋放後門)***
    特徵：中短期均線糾結 ＋ 帶量轉強 ＋ 年線減速改平 (或扣抵牆即將崩塌)
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 計算技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    
    today = df_single.iloc[-1]
    
    # 基底檢查
    is_below_ma240 = today['close'] < today['MA240']
    
    # 當前年線 20 日斜率
    ma240_20d_ago = df_single['MA240'].iloc[-21]
    ma_slope_20d = (today['MA240'] - ma240_20d_ago) / ma240_20d_ago if ma240_20d_ago > 0 else 0
    
    # 均線糾結度檢查
    ma_list = [today['MA5'], today['MA20'], today['MA60']]
    dispersion = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_converged = dispersion < 0.05
    
    # 帶量轉強檢查
    vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
    is_volume_up = today['Trading_Volume'] > vol_ma5 * 1.3 if vol_ma5 > 0 else False
    
    # ==================== 【核心升級：扣抵重力釋放檢查】 ====================
    # 檢查未來 20 天年線丟棄的價格趨勢
    future_deduct_series = df_single['close'].iloc[-240:-220]
    deduct_slope = (future_deduct_series.iloc[-1] - future_deduct_series.iloc[0]) / future_deduct_series.iloc[0]
    
    # 標準條件：橫盤打底的突破, 年線需要極度接近水平（介於 -0.5% 到 +0.5% 之間）
    # 因為右側策略的核心是看「均線糾結度（dispersion < 5%）」和「年線改平（-0.5% 到 +0.5%）」。
    # 此時均線都已經靠攏了，股價自然會離年線非常近，所以負乖離率不需要設得太嚴格，交給均線糾結度去控管即可。        
    is_standard_flattening = -0.005 <= ma_slope_20d <= 0.005
    
    # 扣抵後門：雖然目前年線下彎稍陡 (例如 -0.77%)，但未來 20 天扣抵高價牆正在崩塌 (下墜超過 3%)
    is_deduct_override = (ma_slope_20d > -0.01) and (deduct_slope < -0.03)
    
    if is_standard_flattening:
        is_flattening_slope = True
        status_tag = "[右側突破] 均線糾結+量能表態, 年線已實質改平"
    elif is_deduct_override:
        is_flattening_slope = True
        status_tag = "[右側突破] 均線糾結+量能表態! 年線雖微彎但未來扣抵重力牆已崩塌"
    else:
        is_flattening_slope = False
        status_tag = "未觸發訊號"
    # =====================================================================
    
    is_hit = is_below_ma240 and is_converged and is_volume_up and is_flattening_slope
    status = status_tag if is_hit else "未觸發訊號"
    
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線20日斜率": f"{round(ma_slope_20d * 100, 2)}%",
        "未來20日扣抵坡度": f"{round(deduct_slope * 100, 2)}%",
        "中短期糾結度": f"{round(dispersion * 100, 2)}%",
        "今日量比": f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x",
        "策略狀態": status
    }

    print(f"st_bottom_breakout is_hit:{is_hit} info:{info}")
    return is_hit, info



#以下可以刪除, 已經沒有使用
def st_bottom_rebound(df_single):
    """
    ***底部篩選***年線以下左側錯殺V轉模式或右側突破打底模式
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 計算技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    
    today = df_single.iloc[-1]
    
    # 基底檢查：股價在年線下方
    is_below_ma240 = today['close'] < today['MA240']
    
    # 計算年線 20 日斜率（百分比變動）
    ma240_20d_ago = df_single['MA240'].iloc[-21]
    ma_slope_20d = (today['MA240'] - ma240_20d_ago) / ma240_20d_ago if ma240_20d_ago > 0 else 0
    
    # ==================== 【雙軌獨立判定】 ====================
    
    # ---- 軌道 A：左側急跌錯殺 (V轉模式) ----
    # 條件：負乖離滿足 且 年線不能是「陡峭下跌」（年線在多頭拉回時通常是 > 0 或是非常微幅的 `-0.002`）
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    is_oversold_zone = -0.15 <= dist_ratio <= -0.08
    
    # 多頭拉回的 V 轉：年線斜率只要大於 -0.2% 即可（通常是正數，代表長線趨勢仍向上）
    #is_v_turn_slope = ma_slope_20d > -0.002 
    is_v_turn_slope = ma_slope_20d > -0.01 
    is_track_a_hit = is_oversold_zone and is_v_turn_slope
    
    # ---- 軌道 B：右側打底壓縮 (突破模式) ----
    # 條件：均線糾結 ＋ 帶量轉強 ＋ 年線必須真正「減速改平或上揚」
    ma_list = [today['MA5'], today['MA20'], today['MA60']]
    dispersion = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_converged = dispersion < 0.05
    
    vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
    is_volume_up = today['Trading_Volume'] > vol_ma5 * 1.3 if vol_ma5 > 0 else False
    
    # 橫盤打底的突破：年線需要極度接近水平（介於 -0.5% 到 +0.5% 之間）
    is_flattening_slope = -0.005 <= ma_slope_20d <= 0.005
    is_track_b_hit = is_converged and is_volume_up and is_flattening_slope

    # ==================== 【綜合策略決策】 ====================
    # 只要在年線下，且符合軌道 A 或軌道 B 之一
    is_hit = is_below_ma240 and (is_track_a_hit or is_track_b_hit)
    
    # 狀態標籤
    if is_track_b_hit:
        status = "【右側突破】均線糾結＋量能表態，年線已改平"
    elif is_track_a_hit:
        status = "【左側超跌】多頭拉回錯殺，年線仍維持多頭慣性"
    else:
        status = "未觸發訊號"
    
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線20日斜率": f"{round(ma_slope_20d * 100, 2)}%",
        "中短期糾結度": f"{round(dispersion * 100, 2)}%",
        "今日量比": f"{round(today['Trading_Volume']/vol_ma5, 2) if vol_ma5 > 0 else 0}x",
        "策略狀態": status
    }

    print(f"st_bottom_breakout( df_single ) is_hit:{is_hit} info:{info}")
    
    return is_hit, info
