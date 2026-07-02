from FinMind.data import DataLoader
import pandas as pd
from datetime import datetime, timedelta
import time

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
    is_v_turn_slope = ma_slope_20d > -0.002 
    is_track_a_hit = is_oversold_zone and is_v_turn_slope
    
    # ---- 軌道 B：右側打底壓縮 (突破模式) ----
    # 條件：均線糾結 ＋ 帶量轉強 ＋ 年線必須真正「減速改平或上揚」
    ma_list = [today['MA5'], today['MA20'], today['MA60']]
    dispersion = (max(ma_list) - min(ma_list)) / min(ma_list)
    is_converged = dispersion < 0.05
    
    vol_ma5 = df_single['Trading_Volume'].rolling(5).mean().iloc[-1]
    is_volume_up = today['Trading_Volume'] > vol_ma5 * 1.3 if vol_ma5 > 0 else False
    
    # 橫盤打底的突破：年線需要極度接近水平（介於 -0.5% 到 +0.5% 之間）
    # is_flattening_slope = -0.005 <= ma_slope_20d <= 0.005
    is_flattening_slope = -1.000 <= ma_slope_20d <= 0.005
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
