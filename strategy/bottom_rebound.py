from FinMind.data import DataLoader
import pandas as pd
from datetime import datetime, timedelta
import time

import pandas as pd


import pandas as pd


def st_bottom_v_turn(df_single):
  """***V 轉選股策略（完全依據最新條件一與條件二擇一）***"""
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

  # ==================== 【條件一】 ====================
  # 1. 季線在年線下方
  c1_ma60_below_240 = ma60 < ma240
  # 2. 且年線或季線至少一個走揚（斜率 >= -0.001）
  c1_at_least_one_rising = (ma60_slope >= -0.001) or (ma240_slope >= -0.001)
  # 3. 5日、10日、20日亦在季線下方
  c1_short_below_60 = (ma5 < ma60) and (ma10 < ma60) and (ma20 < ma60)
  # 4. 且 5日、10日、20日形成多頭排列 (MA5 > MA10 > MA20)
  c1_short_bullish = (ma5 > ma10) and (ma10 > ma20)

  cond_1 = (
      c1_ma60_below_240
      and c1_at_least_one_rising
      and c1_short_below_60
      and c1_short_bullish
  )

  # ==================== 【條件二】 ====================
  # 1. 季線在年線下方
  c2_ma60_below_240 = ma60 < ma240
  # 2. 年線斜率走緩接近改平甚至上揚 (>= -0.002)
  c2_ma240_flat_up = ma240_slope >= -0.002
  # 3. 季線在年線下方且已經改平或者走揚 (>= -0.002)
  c2_ma60_flat_up = ma60_slope >= -0.002
  # 4. 收盤高於 5 日線
  c2_close_gt_ma5 = close > ma5
  # 5. 5 日線突破季線 (今日 MA5 > MA60，且昨日 MA5 <= MA60)
  c2_ma5_cross = (ma5 > ma60) and (prev['MA5'] <= prev['MA60'])
  # 6. 5 日線斜度好 (MA5_slope > 0.005)
  c2_ma5_slope = ma5_slope > 0.005
  # 7. 5 日 10日 20日關係：5日高於 10日與 20日線
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
        '[V轉策略] 符合【條件一】(季線在年線下、長線至少一條走揚、5/10/20在季線下且短多排列)'
    )
  elif cond_2:
    status = (
        '[V轉策略] 符合【條件二】(季線在年線下、年季線皆走平或走揚、5日線強勢突破季線且高於10/20日)'
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
