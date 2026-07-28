import pandas as pd

def st_right_side_breakout(df_single, market_above_ma240=True):
  """***右側交易突破選股策略（優化版：新增新增乖離率與盤整扎實度過濾與大盤年線過濾與乖離率防禦）***"""
    
  # 🌟 核心阻擋：若大盤在年線之下，右側突破策略直接不予觸發
  if not market_above_ma240:
    return False, {}

  if df_single.empty or len(df_single) < 120:
    return False, {}

  df_single = df_single.copy()

  # 計算各天期移動平均線
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA10'] = df_single['close'].rolling(10).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()  # 季線
  df_single['MA240'] = df_single['close'].rolling(240).mean()  # 年線

  # 計算成交量 20 日均量
  df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()

  # 計算 20 日價格最高價與最低價（用以判斷突破與區間振幅）
  df_single['Max_20'] = df_single['max'].shift(1).rolling(20).max()
  df_single['Min_20'] = df_single['min'].shift(1).rolling(20).min()

  # 【新增】計算 20 日均線乖離率 (Bias) = (收盤價 - MA20) / MA20
  df_single['Bias_20'] = (df_single['close'] - df_single['MA20']) / df_single['MA20']

  # 【新增】計算過去 20 日區間振幅 (Range%) = (20日最高 - 20日最低) / MA20
  df_single['Range_20'] = (df_single['Max_20'] - df_single['Min_20']) / df_single['MA20']

  # 計算均線斜率
  df_single['MA20_slope'] = (
      df_single['MA20'] - df_single['MA20'].shift(20)
  ) / df_single['MA20'].shift(20)
  df_single['MA60_slope'] = (
      df_single['MA60'] - df_single['MA60'].shift(20)
  ) / df_single['MA60'].shift(20)
  df_single['MA5_slope'] = (
      df_single['MA5'] - df_single['MA5'].shift(5)
  ) / df_single['MA5'].shift(5)

  today = df_single.iloc[-1]
  prev = df_single.iloc[-2]

  if pd.isna([today['MA20'], today['MA60'], today['MA5']]).any():
    return False, {}

  close = today['close']
  max_20 = today['Max_20']
  volume = today['Trading_Volume']
  vol_ma20 = today['Vol_MA20']
  ma5 = today['MA5']
  ma10 = today['MA10']
  ma20 = today['MA20']
  ma60 = today['MA60']
  ma240 = today['MA240']
  ma20_slope = today['MA20_slope']
  ma60_slope = today['MA60_slope']
  ma5_slope = today['MA5_slope']
  bias_20 = today['Bias_20']
  range_20 = today['Range_20']

  # ==================== 【條件一：箱型突破與量能爆發防禦版】 ====================
  c1_breakout = close > max_20
  c1_volume_surge = volume >= (vol_ma20 * 1.5)
  c1_bullish_alignment = (ma5 > ma10) and (ma10 > ma20) and (ma20 > ma60)
  c1_ma_rising = (ma20_slope >= 0.0) and (ma60_slope >= 0.0)
  
  if len(df_single) >= 240 and not pd.isna(ma240):
    c1_above_ma240 = close > ma240
  else:
    c1_above_ma240 = True

  # 【新增防禦 1】乖離率過濾：收盤價高於 20MA 超過 12% 視為短線過熱，不予追價
  c1_bias_safe = bias_20 <= 0.12  # 可依回測結果調整為 0.10 ~ 0.15

  # 【新增防禦 2】盤整區間扎實度：前 20 日區間振幅應小於 25%，確保是有效收斂打底
  c1_consolidation_tight = range_20 <= 0.25

  cond_1 = (
      c1_breakout
      and c1_volume_surge
      and c1_bullish_alignment
      and c1_ma_rising
      and c1_above_ma240
      and c1_bias_safe              # <--- 新增乖離率過熱防禦
      and c1_consolidation_tight    # <--- 新增盤整區間扎實度過濾
  )

  # ==================== 【條件二：短線強勢動能與均線交叉發散版】 ====================
  c2_close_gt_ma5 = close > ma5
  c2_ma5_cross_20 = (ma5 > ma20) and (prev['MA5'] <= prev['MA20'])
  c2_ma5_slope_strong = ma5_slope >= 0.005
  c2_short_bullish = (ma5 > ma10) and (ma10 > ma20)
  c2_ma20_safe = ma20_slope >= -0.001

  # 同樣可對條件二加上乖離率限制，避免黃金交叉時已經噴出太遠
  c2_bias_safe = bias_20 <= 0.10

  cond_2 = (
      c2_close_gt_ma5
      and c2_ma5_cross_20
      and c2_ma5_slope_strong
      and c2_short_bullish
      and c2_ma20_safe
      and c2_bias_safe              # <--- 新增乖離率防禦
  )

  # ==================== 【綜合判定與狀態標註】 ====================
  is_hit = cond_1 or cond_2

  if cond_1 and cond_2:
    status = '[右側策略] 同時符合【條件一】與【條件二】'
  elif cond_1:
    status = '[右側策略] 符合【條件一】(突破20日新高、量價齊揚、乖離健康與區間收斂)'
  elif cond_2:
    status = '[右側策略] 符合【條件二】(短線強勢動能與均線黃金交叉)'
  else:
    status = '未觸發右側訊號'

  recent_low = df_single['close'].iloc[-10:].min()

  info = {
      '收盤': close,
      '5日線': round(ma5, 2),
      '20日線(MA20)': round(ma20, 2),
      '季線(MA60)': round(ma60, 2),
      '20MA乖離率': f'{round(bias_20 * 100, 2)}%',
      '20日區間振幅': f'{round(range_20 * 100, 2)}%',
      '建議停損參考價': recent_low,
      '策略狀態': status,
  }

  return is_hit, info

def st_right_side_breakout_2026072801(df_single):
  """***右側交易突破選股策略（條件一：強勢突破創高與量價齊揚防禦；條件二：均線發散與動能確認）***"""
  if df_single.empty or len(df_single) < 120:
    return False, {}

  df_single = df_single.copy()

  # 計算各天期移動平均線
  df_single['MA5'] = df_single['close'].rolling(5).mean()
  df_single['MA10'] = df_single['close'].rolling(10).mean()
  df_single['MA20'] = df_single['close'].rolling(20).mean()
  df_single['MA60'] = df_single['close'].rolling(60).mean()  # 季線
  df_single['MA240'] = df_single['close'].rolling(240).mean()  # 年線

  # 計算成交量 20 日均量
  df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()

  # 計算 20 日價格最高價（不含當日，用以判斷突破前高）
  df_single['Max_20'] = df_single['max'].shift(1).rolling(20).max()

  # 計算均線 20 日斜率
  df_single['MA20_slope'] = (
      df_single['MA20'] - df_single['MA20'].shift(20)
  ) / df_single['MA20'].shift(20)
  df_single['MA60_slope'] = (
      df_single['MA60'] - df_single['MA60'].shift(20)
  ) / df_single['MA60'].shift(20)

  # 計算 5 日線 5 日斜率
  df_single['MA5_slope'] = (
      df_single['MA5'] - df_single['MA5'].shift(5)
  ) / df_single['MA5'].shift(5)

  today = df_single.iloc[-1]
  prev = df_single.iloc[-2]

  # 防禦性檢查
  if pd.isna([today['MA20'], today['MA60'], today['MA5']]).any():
    return False, {}

  close = today['close']
  max_20 = today['Max_20']
  volume = today['Trading_Volume']
  vol_ma20 = today['Vol_MA20']
  ma5 = today['MA5']
  ma10 = today['MA10']
  ma20 = today['MA20']
  ma60 = today['MA60']
  ma240 = today['MA240']
  ma20_slope = today['MA20_slope']
  ma60_slope = today['MA60_slope']
  ma5_slope = today['MA5_slope']

  # ==================== 【條件一：箱型突破與量能爆發防禦版】 ====================
  # 1. 價格突破過去 20 日最高價
  c1_breakout = close > max_20

  # 2. 量能確認：當日成交量大於 20 日均量 1.5 倍以上
  c1_volume_surge = volume >= (vol_ma20 * 1.5)

  # 3. 趨勢多頭排列：短期與中期均線向上發散 (MA5 > MA10 > MA20 > MA60)
  c1_bullish_alignment = (ma5 > ma10) and (ma10 > ma20) and (ma20 > ma60)

  # 4. 均線斜率向上防禦：20日與60日均線皆必須向上（斜率 >= 0）
  c1_ma_rising = (ma20_slope >= 0.0) and (ma60_slope >= 0.0)

  # 5. 遠離底部防禦：收盤價高於年線（若有 240 天資料時檢查）
  if len(df_single) >= 240 and not pd.isna(ma240):
    c1_above_ma240 = close > ma240
  else:
    c1_above_ma240 = True

  cond_1 = (
      c1_breakout
      and c1_volume_surge
      and c1_bullish_alignment
      and c1_ma_rising
      and c1_above_ma240
  )

  # ==================== 【條件二：短線強勢動能與均線交叉發散版】 ====================
  # 1. 收盤價站穩 5 日線之上
  c2_close_gt_ma5 = close > ma5

  # 2. 5日線向上穿越 20 日線（黃金交叉或發散初期）
  c2_ma5_cross_20 = (ma5 > ma20) and (prev['MA5'] <= prev['MA20'])

  # 3. 5日線斜率強勢（斜率 >= 0.005）
  c2_ma5_slope_strong = ma5_slope >= 0.005

  # 4. 均線多頭排列 (MA5 > MA10 > MA20)
  c2_short_bullish = (ma5 > ma10) and (ma10 > ma20)

  # 5. 20日均線走平或向上 (斜率 >= -0.001)
  c2_ma20_safe = ma20_slope >= -0.001

  cond_2 = (
      c2_close_gt_ma5
      and c2_ma5_cross_20
      and c2_ma5_slope_strong
      and c2_short_bullish
      and c2_ma20_safe
  )

  # ==================== 【綜合判定與狀態標註】 ====================
  is_hit = cond_1 or cond_2

  if cond_1 and cond_2:
    status = '[右側策略] 同時符合【條件一】與【條件二】'
  elif cond_1:
    status = (
        '[右側策略] 符合【條件一】(突破20日新高、量能放大>=1.5倍、'
        '均線多頭發散 MA5>MA10>MA20>MA60、均線向上且站上年線)'
    )
  elif cond_2:
    status = (
        '[右側策略] 符合【條件二】(站穩5日線、MA5帶量穿越MA20、'
        '5日線強勢斜率、短均多頭排列)'
    )
  else:
    status = '未觸發右側訊號'

  # 計算近期右側追價停損參考價（例如過去 10 天最低價或 20MA）
  recent_low = df_single['close'].iloc[-10:].min()

  info = {
      '收盤': close,
      '5日線': round(ma5, 2),
      '20日線(MA20)': round(ma20, 2),
      '季線(MA60)': round(ma60, 2),
      '20日線20日斜率': f'{round(ma20_slope * 100, 2)}%',
      '季線20日斜率': f'{round(ma60_slope * 100, 2)}%',
      '5日線5日斜率': f'{round(ma5_slope * 100, 2)}%',
      '建議停損參考價': recent_low,
      '策略狀態': status,
  }

  return is_hit, info



def st_bottom_u_turn_2026071101(df_single):
    """
    ***策略 A-2：題材破滅 U 型碗底翻揚系統 (20260711 究極嚴選 U 型底版)***
    
    優化重點回顧：
    1. 雙扣抵容許區間 ➡️ 留下華碩，洗掉結構不穩股。
    2. 均線發散度限制 ➡️ 洗掉短線暴衝、均線拉太開的個股。
    3. [新增] 歷史最大回撤限制 ➡️ 確保個股「左側狠跌過」，剔除抗跌橫盤平台股。
    4. [新增] 季線年線深層位階 ➡️ 確保個股處於「中長線深層底部」，剔除貼著年線整理股。
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # ==========================================
    # 1. 技術指標計算
    # ==========================================
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # ==========================================
    # 2. 【核心新增】真正 U 型底形態檢查 (碗壁與深度過濾)
    # ==========================================
    # 🌟 條件 A：歷史最大回撤限制（定義 U 型底的「左側碗壁」）
    # 尋找過去 1 年（約 240 個交易日）的歷史最高價，要求目前股價至少要從高點深幅修正 20% 以上
    # 這樣可以直接擋掉廣達這種在大盤大跌時、自己卻橫盤頂天根本沒跌的抗跌平台股
    max_price_1y = df_single['max'].rolling(240).max().iloc[-1]
    drop_from_top = (max_price_1y - today['close']) / max_price_1y if max_price_1y > 0 else 0
    is_real_drop_1y = drop_from_top >= 0.20  # 門檻設為 20%，確保左側有因題材破滅而狠跌過的軌跡

    # 🌟 條件 B：中長線深層底部限制（定義 U 型底的「碗底深處」）
    # 要求代表中線的季線（MA60）必須在年線（MA240）下方至少 5% 以上，確保中長線位階夠低
    # 廣達觸發時因長線過於強勢，季線與年線幾乎黏在一起（小於 1%），補上此條可徹底洗掉「假築底、真橫盤」的股票
    is_deep_bottom = (today['MA240'] - today['MA60']) / today['MA240'] >= 0.05

    # ==========================================
    # 3. 基本位階與趨勢檢查
    # ==========================================
    # 季線在年線下方，代表中線仍處底部的基本設定
    is_below_ma240 = today['MA60'] < today['MA240']
    
    # 檢查年線（MA240）斜率是否趨於走平，代表長期賣壓已經告一段落
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.01 
    
    # 短中線多頭排列且季線開始上揚，代表碗底開始「探頭翻揚」
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    
    # ==========================================
    # 4. 歷史優化條件檢查
    # ==========================================
    # 🌟 優化一：扣抵值智能容許過濾 (避免個股因為扣抵值短暫拉高而被策略誤殺)
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    ma60_deduct_change = (ma60_deduct_5d_later - ma60_deduct_today) / ma60_deduct_today if ma60_deduct_today > 0 else 0
    is_ma60_deduct_ok = ma60_deduct_change <= 0.015

    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220]
    ma240_deduct_change = (ma240_deduct_20d_later - ma240_deduct_today) / ma240_deduct_today if ma240_deduct_today > 0 else 0
    is_ma240_deduct_ok = ma240_deduct_change <= 0.02
    
    # 🌟 優化二：均線發散度過濾 (洗掉短線已經暴衝、均線拉太開的過熱股票)
    ma_list = [today['MA5'], today['MA10'], today['MA20']]
    ma_dispersion = (max(ma_list) - min(ma_list)) / today['MA20'] if today['MA20'] > 0 else 0
    is_ma_not_overheated = ma_dispersion <= 0.06  # 限制短中期均線乖離在 6% 以內，確保均線溫和凝聚

    # ==========================================
    # 5. 量能與當日觸發判定
    # ==========================================
    is_triggered = today['close'] > today['open'] # 當日收紅 K 棒做為右側發動訊號
    
    # ==========================================
    # 6. 綜合判定（加入所有新舊核心條件）
    # ==========================================
    is_hit = (is_real_drop_1y and is_deep_bottom and                      # 🎯 碗壁與碗底形態過濾
              is_below_ma240 and is_ma240_stable and is_ma60_turning_up and # 趨勢位階
              is_short_trend_bullish and is_triggered and                  # 短線發動
              is_ma60_deduct_ok and is_ma240_deduct_ok and is_ma_not_overheated) # 扣抵與凝聚優化

    # Debug 訊息輸出
    print(f"--- 形態檢查 ---")
    print(f"RealDrop1Y(>=20%): {is_real_drop_1y} (實際跌幅: {round(drop_from_top*100,2)}%)")
    print(f"DeepBottom(>=5%): {is_deep_bottom} (年季線差距: {round(((today['MA240']-today['MA60'])/today['MA240'])*100,2)}%)")
    print(f"--- 趨勢與技術面檢查 ---")
    print(f"Below240: {is_below_ma240} | Stable240: {is_ma240_stable} | MA60Up: {is_ma60_turning_up} | ShortBull: {is_short_trend_bullish} | Triggered: {is_triggered}")
    print(f"ma60_deduct: {is_ma60_deduct_ok} | ma240_deduct: {is_ma240_deduct_ok} | not_overheated: {is_ma_not_overheated}")
    
    status = "[A-2 鑽石碗底] 均線溫和凝聚＋雙扣抵大吉！" if is_hit else "未觸發訊號"
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    info = {
        "收盤": today['close'],
        "均線發散度": f"{round(ma_dispersion * 100, 2)}%",
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "策略狀態": status
    }
        
    return is_hit, info


# ==============================================================================
# 💡 策略邏輯備忘註腳 (Strategy Footnotes & Design Philosophy)
# ==============================================================================
# 1. 核心哲學：專門拯救「進場後慘遭惡意大甩轎」的冤枉停損頂級飆股（如緯穎、技嘉、台光電）。
# 2. 認證機制：這類標的在甩轎前通常已經展現過「初升段的攻擊性」，因此季線(MA60)通常已經
#    開始翻揚、甚至與年線(MA240)黃金交叉。我們不再限制「MA60 < MA240」，改以年線走平為底。
# 3. 甩轎判定：在過去 30 天內（一個月內），股價從波段高點往下狠狠「往回砸盤達 -10% 至 -30%」，
#    這種無情的埋殺會逼迫所有按照紀律操作的散戶（如 -10% 停損者）集體繳械、冤枉出場。
# 4. 今日復活點：主力洗盤結束後再度發動點火。今日必須符合「實體紅K」、「爆量 1.5 倍」、
#    「收盤強勢重新站回季線（生命線）」並且「收盤創 20 日新高」取得右側動能確認，發動鳳凰接回。
# ==============================================================================

def st_shakeout_resurrection(df_single):
    """惡意甩轎復活策略
    
    【系統欄位對接】: 原始最低價欄位使用 'min'，最高價欄位使用 'max' (對齊你的資料庫規格)
    """
    try:
        # 1. 基礎長度防護門檻（確保滿足 MA240 與 90 日大滾動窗格需求）
        if len(df_single) < 330:
            return False, {"策略狀態": "資料天數不足(<330)"}
            
        # =========================================================================
        # 🔧 策略內部獨立運算：不依賴外層，自給自足
        # =========================================================================
        df_single['MA60'] = df_single['close'].rolling(60).mean()
        df_single['MA240'] = df_single['close'].rolling(240).mean()
        df_single['MA5_volume'] = df_single['Trading_Volume'].rolling(5).mean()
        df_single['MA20_volume'] = df_single['Trading_Volume'].rolling(20).mean()
            
        # 定義時間指針：永遠鎖定最後一列（今日最新數據）
        today = df_single.iloc[-1]
        today_ma5_vol = df_single['MA5_volume'].iloc[-1]

        # =========================================================================
        # 核心條件一：大趨勢底定濾網（年線減速走平 + 今日重新站回生命線）
        # =========================================================================
        # 條件 A: 年線走平 (確保不是處於末跌段的無底深淵，年線 5 日斜率收斂至 -1.5% 以內)
        ma240_5d_ago = df_single['MA240'].iloc[-5]
        ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago
        is_ma240_flattening = ma240_slope_5d >= -0.015
        
        # 條件 B: 今日實體強勢站回/守住生命線 (收盤價必須大於等於季線)
        is_above_lifeline = today['close'] >= today['MA60']
        
        if not (is_ma240_flattening and is_above_lifeline):
            return False, {"策略狀態": "初階型態不符（年線尚未走平或收盤未站上季線）"}

        # =========================================================================
        # 核心條件二：30 天時空記憶體 —— 惡意大甩轎判定（專抓 -10% 到 -30% 的血洗區）
        # =========================================================================
        # 觀測窗格：切出過去 30 天 (不含今天) 的歷史 K 線
        past_30d_window = df_single.iloc[-31:-1]
        
        # 找出過去 30 天內的最高價與最低價
        past_30d_max = past_30d_window['max'].max()
        past_30d_min = past_30d_window['min'].min()
        
        # 核心計算：計算這一個月內「最大甩轎回撤幅度」
        # 理論：從這 30 天的最高點一路往下砸到最低點，回撤幅度有多深？
        shakeout_drop_pct = (past_30d_min - past_30d_max) / past_30d_max
        
        # 判定：最大回撤必須落在 -10% 到 -30% 之間（剛好狠狠震碎常規技術面停損單，但又不是崩盤股）
        has_violent_shakeout = -0.30 <= shakeout_drop_pct <= -0.095
        
        if not has_violent_shakeout:
            return False, {"策略狀態": "30日觀測期內未見符合幅度的惡意大甩轎型態"}

        # =========================================================================
        # 核心條件三：今日總攻判定（王者回歸、鳳凰接回點）
        # =========================================================================
        # 條件 A: 今日收盤價一舉創下過去 20 日的新高（確認甩轎坑底結束，右側動能爆發）
        max_price_20d = df_single['close'].iloc[-21:-1].max()
        is_price_breakout_20d = today['close'] >= max_price_20d
        
        # 條件 B: 今日收盤必須是實體紅K (收盤價高於開盤價)
        is_today_positive = today['close'] > today['open']
        
        # 條件 C: 主力再度發動爆量點火 (今日成交量大於 5 日均量的 1.5 倍)
        is_volume_signal_up = today['Trading_Volume'] >= today_ma5_vol * 1.5
        
        # 分流狀態提示
        if not is_price_breakout_20d:
            return False, {"策略狀態": "已遭大甩轎，但今日股價尚未創20日新高（仍在坑底盤整）"}
            
        if not (is_today_positive and is_volume_signal_up):
            return False, {"策略狀態": "已遭大甩轎、股價已突破，但今日總攻紅K未見主力爆量點火"}
            
        # =========================================================================
        # 🎯 觸發成功：打包回傳數據（完美對接外層 hit_row.update）
        # =========================================================================
        if is_price_breakout_20d and is_today_positive and is_volume_signal_up:
            
            today_change = round(((today['close'] - today['open']) / today['open']) * 100, 2)
            # 將停損價設在過去 30 天大甩轎陰影坑底的最低防線 -1%
            stop_loss_price = round(past_30d_min * 0.99, 2)
            stop_loss_pct = round(((stop_loss_price - today['close']) / today['close']) * 100, 2)
            
            detail_info = {
                "策略狀態": "完全觸發（惡意甩轎後強勢復活）",
                "今日收盤": today['close'],
                "今日K線漲幅": f"{today_change}%",
                "甩轎區最高價": past_30d_max,
                "甩轎坑底最低價": past_30d_min,
                "一個月內最大甩幅": f"{round(shakeout_drop_pct * 100, 2)}%",
                "建議保命停損價": stop_loss_price,
                "預估停損幅度": f"{stop_loss_pct}%",
                "進場時年線斜率": f"{round(ma240_slope_5d * 100, 2)}%"
            }
            return True, detail_info

    except Exception as e:
        stock_code = df_single['stock_id'].iloc[0] if 'stock_id' in df_single.columns else '未知'
        print(f"⚠️ [策略異常跳過] 股票代號 {stock_code} 發生錯誤: {str(e)}")
        return False, {"策略狀態": f"計算異常跳過 ({str(e)})"}
        
    return False, {"策略狀態": "未知異常狀態"}

# ==============================================================================
# 💡 策略邏輯備忘註腳 (Strategy Footnotes & Design Philosophy)
# ==============================================================================
# 1. 核心哲學：本策略專門捕捉「破底翻」或「惡意洗盤後 V 型拔地而起」的暴利黑馬股。
# 2. 徹底揚棄「左側摸底」的左側猜測，改用今日「實體紅K 創 20 日新高」作為右側動能確認的進場依據。
# 3. 承認並解鎖「洗盤時差 (Washout Lag)」：
#    - 主力在拉抬前，往往會利用市場恐慌，刻意砸盤殺破「前 60 日歷史新低」(製造崩盤假象)。
#    - 關鍵在於：洗盤當天成交量必須呈現「窒息量縮」(代表籌碼已被主力鎖死，散戶絕望繳械)。
#    - 隨後主力迅速在 10 天之內發動總攻，拉出爆量長紅並一舉強勢站回季線（生命線）。
#    - 因此，本策略引進「時空記憶體」，只要過去 30 天(一個半月)曾出現主力惡意挖坑洗盤的足跡，
#      搭配「今日」主力爆量點火、價格全面復活，即視為最完美的短線右側發動點。
# ==============================================================================

def st_washout_phoenix(df_single):
    """強力洗盤復活策略 (鳳凰涅槃定錨版)
    
    【系統欄位對接】: 已將原始最低價欄位由 'low' 修正為你系統官方的 'min'
    """
    try:
        if len(df_single) < 330: # 確保滿足 MA240 與 90 日滾動窗格需求
            return False, {"策略狀態": "資料天數不足(<330)"}
            
        # =========================================================================
        # 🔧 策略內部獨立運算：自給自足
        # =========================================================================
        df_single['MA60'] = df_single['close'].rolling(60).mean()
        df_single['MA240'] = df_single['close'].rolling(240).mean()
        df_single['MA5_volume'] = df_single['Trading_Volume'].rolling(5).mean()
        df_single['MA20_volume'] = df_single['Trading_Volume'].rolling(20).mean()
            
        today = df_single.iloc[-1]
        today_ma5_vol = df_single['MA5_volume'].iloc[-1]
        today_ma20_vol = df_single['MA20_volume'].iloc[-1]

        # =========================================================================
        # 核心條件一：大底部型態濾網（年線走平 + 股價站上季線）
        # =========================================================================
        # 條件 A: 年線下彎速度走平 (確保引力衰減中)
        ma240_5d_ago = df_single['MA240'].iloc[-5]
        ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago
        is_ma240_flattening = ma240_slope_5d >= -0.015  # 下跌斜率收斂在 -1.5% 以內
        
        # 條件 B: 今日實體強勢站回生命線 (今日收盤價必須站上季線)
        is_above_lifeline = today['close'] >= today['MA60']
        
        if not (is_ma240_flattening and is_above_lifeline):
            return False, {"策略狀態": "底部均線型態不符（年線未走平或未站上季線）"}

        # =========================================================================
        # 核心條件二：30 天時空記憶體（對接 min 欄位，捕捉大甩轎破底翻）
        # =========================================================================
        # 觀測窗格：切出過去 30 天 (不含今天) 的歷史 K 線
        past_30d_window = df_single.iloc[-31:-1]
        
        # 找出洗盤發生前、更早的 60 日最低價邊界（使用對接欄位 'min'）
        historical_60d_min_low = df_single['min'].iloc[-91:-31].min()
        
        # 判定 A: 過去 30 天內，最低價必須「曾經跌破」之前的 60 日歷史低點
        past_min_low = past_30d_window['min'].min()
        has_washout_drop = past_min_low <= historical_60d_min_low
        
        # 判定 B: 找出甩轎那天的窒息量
        # （使用相對位置 argmin 與 iloc 絕對定錨，避開交易日 Index 衝突）
        washout_relative_pos = past_30d_window['min'].values.argmin() 
        absolute_pos = len(df_single) - 31 + washout_relative_pos
        
        washout_day_volume = df_single['Trading_Volume'].iloc[absolute_pos]
        washout_day_ma20_vol = df_single['MA20_volume'].iloc[absolute_pos]
        
        is_washout_volume_low = washout_day_volume < washout_day_ma20_vol * 0.8
        
        if not (has_washout_drop and is_washout_volume_low):
            return False, {"策略狀態": "30日觀測期內未見洗盤訊號（未創低或未見窒息量）"}

        # =========================================================================
        # 核心條件三：今日總攻判定（全面復活）
        # =========================================================================
        # 條件 A: 今日收盤價一舉創下過去 20 日的新高
        max_price_20d = df_single['close'].iloc[-21:-1].max()
        is_price_breakout_20d = today['close'] >= max_price_20d
        
        # 條件 B: 今日收盤必須是實體紅K (收盤價高於開盤價)
        is_today_positive = today['close'] > today['open']
        
        # 條件 C: 主力發動爆量點火 (今日成交量大於 5 日均量的 1.5 倍)
        is_volume_signal_up = today['Trading_Volume'] >= today_ma5_vol * 1.5
        
        if not is_price_breakout_20d:
            return False, {"策略狀態": "進入潛伏觀測區（已惡意洗盤，但今日股價未創20日新高）"}
            
        if not (is_today_positive and is_volume_signal_up):
            return False, {"策略狀態": "進入潛伏觀測區（已惡意洗盤、股價突破，但今日紅K未爆量）"}
            
        # =========================================================================
        # 🎯 觸發成功：打包回傳數據（完美對接外層 hit_row.update）
        # =========================================================================
        if is_price_breakout_20d and is_today_positive and is_volume_signal_up:
            
            today_change = round(((today['close'] - today['open']) / today['open']) * 100, 2)
            stop_loss_price = round(past_min_low * 0.99, 2)
            stop_loss_pct = round(((stop_loss_price - today['close']) / today['close']) * 100, 2)
            
            detail_info = {
                "策略狀態": "完全觸發（帶量紅K破底翻）",
                "今日收盤": today['close'],
                "今日K線漲幅": f"{today_change}%",
                "洗盤區最低價": past_min_low,
                "建議保命停損價": stop_loss_price,
                "預估停損幅度": f"{stop_loss_pct}%",
                "進場時年線斜率": f"{round(ma240_slope_5d * 100, 2)}%"
            }
            return True, detail_info

    except Exception as e:
        stock_code = df_single['stock_id'].iloc[0] if 'stock_id' in df_single.columns else '未知'
        print(f"⚠️ [策略異常跳過] 股票代號 {stock_code} 發生錯誤: {str(e)}")
        return False, {"策略狀態": f"計算異常跳過 ({str(e)})"}
        
    return False, {"策略狀態": "未知異常狀態"}

# ==============================================================================
# 💡 策略邏輯備忘註腳 (Strategy Footnotes & Design Philosophy)
# ==============================================================================
# 1. 核心哲學：本策略專門捕捉「U 型底」或「地下室破冰」的轉骨黑馬股。
# 2. 徹底揚棄「前波高點」的時空猜測，改用中長線均線的「絕對乖離度」作為空間防守依據。
# 3. 承認並解鎖「價量時差 (Time Lag)」：
#    - 主力往往在底部最絕望、均線仍下彎時敲進「定海神針」的大量 (此時型態不符)。
#    - 隨後溫和量縮橫盤，等到季線轉強、年線減速時，當天成交量通常已趨於平淡 (此時無大量)。
#    - 因此，本策略引進「時空記憶體」，只要過去 20 天(一個月)曾有主力爆量足跡，
#      搭配「今日」價格與均線結構正式到位，即視為完美的波段買點。
# ==============================================================================

def st_bottom_u_turn_with_memory(df_single):
    """
    ***st_bottom_u_turn 策略 A-5：解鎖價量時差的「主力痕跡記憶系統」***
    
    【核心邏輯優化】
    - 拋棄「爆量與均線必須在同一天」的死板限制。
    - 記憶濾網：過去 20 天內曾出現過 > 20日均量 2.0 倍的紅K爆量，程式會記住此主力腳印。
    - 收網觸發：今日剛好走到「季線探頭、年線減速、價格創 60 日新高」的翻揚臨界點，立刻觸發。
    
    - 比st_bottom_u_turn_with_memory_20260711_01增加扣抵值濾網
    """
    if df_single.empty or len(df_single) < 250:
        return False, {}

    # --- 1. 計算基本技術指標 ---
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 流動性基本防禦
    if today['Vol_MA20'] < 300:
        return False, {}

    # --- 2. 主力爆量記憶體 (解鎖價量時差) ---
    # 計算每一天是否「成交量 >= 20日均量的 2.0 倍 且 當天收紅K」
    df_single['is_volume_burst'] = (df_single['Trading_Volume'] >= df_single['Vol_MA20'] * 2.0) & (df_single['close'] > df_single['open'])
    
    # 檢查「過去 20 個交易日（約一個月）」內，有沒有任何一天觸發過爆量
    has_volume_memory_20d = df_single['is_volume_burst'].rolling(20).max().iloc[-1] == 1.0

    # --- 3. 空間防守：季線在年線下方至少 8% 之外 (絕對低檔位階，免用前波高點) ---
    ma_gap_ratio = today['MA60'] / today['MA240'] if today['MA240'] > 0 else 1.0
    is_deep_enough = ma_gap_ratio <= 0.92  
    
    # --- 4. 價格實質突破：創 60 日（一季）最高收盤價，突破碗底頸線 ---
    max_close_60d = df_single['close'].iloc[-61:-1].max()
    is_price_breakout = today['close'] > max_close_60d
    
    # --- 5. 趨勢轉折與年線減速 (今天收網的技術條件) ---
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago != 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.015
    
    # 今日基本動能：不求今天暴巨量，但今天至少要是個多頭前進的收紅盤
    is_today_positive = today['close'] >= yesterday['close']

    # === 新增：年線扣抵值防禦濾網 ===
    # 找出 240 天前的股價（即今日 MA240 的扣抵位置）
    # 為了防止高價股高檔套牢壓力，未來 20 天的扣抵值（240天前~220天前）也必須納入考量
    ref_idx_240 = -240
    ref_idx_220 = -220
    
    if len(df_single) >= 240:
        price_240d_ago = df_single['close'].iloc[ref_idx_240]
        # 未來一個月內會扣抵到的最高價
        max_charge_price_next_month = df_single['close'].iloc[ref_idx_240:ref_idx_220].max()
        
        # 【核心防禦條件】: 今日股價如果距離未來一個月要扣抵的最高價「太遠」（例如跌幅超過 40%）
        # 代表一年前的今天是一座高不可攀的大山，年線在未來一個月「絕對不可能扣平」，只會加速下墜！
        is_charge_safe = today['close'] >= (max_charge_price_next_month * 0.55) # 至少要在扣抵最高價的 55% 以上
    else:
        is_charge_safe = False

    # === 結合原本的判定 ===
    is_hit = (has_volume_memory_20d and is_deep_enough and is_price_breakout and 
              is_ma60_turning_up and is_ma240_stable and is_today_positive and
              is_charge_safe) # 🌟 只有扣抵安全才准觸發
              
    # 找出過去 20 天最高的那次量能倍數，方便在 log 中觀察主力力道
    df_single['vol_ratio_track'] = df_single['Trading_Volume'] / df_single['Vol_MA20']
    max_vol_ratio_20d = df_single['vol_ratio_track'].rolling(20).max().iloc[-1]

    info = {
        "收盤": today['close'],
        "季線/年線比": f"{round(ma_gap_ratio * 100, 2)}%",
        "突破60日高點": is_price_breakout,
        "過去一個月有主力訊號": "有" if has_volume_memory_20d else "無",
        "期間最大主力波段量": f"{round(max_vol_ratio_20d, 2)}x",
        "今日量比20MA": f"{round(today['Trading_Volume'] / today['Vol_MA20'], 2)}x",
        "策略狀態": "【時差解鎖】主力潛伏完畢，今日結構正式轉強！" if is_hit else "未觸發"
    }
    
    return is_hit, info


def st_bottom_u_turn_with_memory_20260711_01(df_single):
    """
    ***st_bottom_u_turn 策略 A-5：解鎖價量時差的「主力痕跡記憶系統」***
    
    【核心邏輯優化】
    - 拋棄「爆量與均線必須在同一天」的死板限制。
    - 記憶濾網：過去 20 天內曾出現過 > 20日均量 2.0 倍的紅K爆量，程式會記住此主力腳印。
    - 收網觸發：今日剛好走到「季線探頭、年線減速、價格創 60 日新高」的翻揚臨界點，立刻觸發。
    無扣抵值濾網
    """
    if df_single.empty or len(df_single) < 250:
        return False, {}

    # --- 1. 計算基本技術指標 ---
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA20'] = df_single['Trading_Volume'].rolling(20).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 流動性基本防禦
    if today['Vol_MA20'] < 300:
        return False, {}

    # --- 2. 主力爆量記憶體 (解鎖價量時差) ---
    # 計算每一天是否「成交量 >= 20日均量的 2.0 倍 且 當天收紅K」
    df_single['is_volume_burst'] = (df_single['Trading_Volume'] >= df_single['Vol_MA20'] * 2.0) & (df_single['close'] > df_single['open'])
    
    # 檢查「過去 20 個交易日（約一個月）」內，有沒有任何一天觸發過爆量
    has_volume_memory_20d = df_single['is_volume_burst'].rolling(20).max().iloc[-1] == 1.0

    # --- 3. 空間防守：季線在年線下方至少 8% 之外 (絕對低檔位階，免用前波高點) ---
    ma_gap_ratio = today['MA60'] / today['MA240'] if today['MA240'] > 0 else 1.0
    is_deep_enough = ma_gap_ratio <= 0.92  
    
    # --- 4. 價格實質突破：創 60 日（一季）最高收盤價，突破碗底頸線 ---
    max_close_60d = df_single['close'].iloc[-61:-1].max()
    is_price_breakout = today['close'] > max_close_60d
    
    # --- 5. 趨勢轉折與年線減速 (今天收網的技術條件) ---
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago != 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.015
    
    # 今日基本動能：不求今天暴巨量，但今天至少要是個多頭前進的收紅盤
    is_today_positive = today['close'] >= yesterday['close']
    
    # --- 6. 綜合判定 ---
    is_hit = (has_volume_memory_20d and is_deep_enough and is_price_breakout and 
              is_ma60_turning_up and is_ma240_stable and is_today_positive)
              
    # 找出過去 20 天最高的那次量能倍數，方便在 log 中觀察主力力道
    df_single['vol_ratio_track'] = df_single['Trading_Volume'] / df_single['Vol_MA20']
    max_vol_ratio_20d = df_single['vol_ratio_track'].rolling(20).max().iloc[-1]

    info = {
        "收盤": today['close'],
        "季線/年線比": f"{round(ma_gap_ratio * 100, 2)}%",
        "突破60日高點": is_price_breakout,
        "過去一個月有主力訊號": "有" if has_volume_memory_20d else "無",
        "期間最大主力波段量": f"{round(max_vol_ratio_20d, 2)}x",
        "今日量比20MA": f"{round(today['Trading_Volume'] / today['Vol_MA20'], 2)}x",
        "策略狀態": "【時差解鎖】主力潛伏完畢，今日結構正式轉強！" if is_hit else "未觸發"
    }
    
    return is_hit, info


def st_bottom_u_turn(df_single):
    """
    ***st_bottom_u_turn 策略 A-2：題材破滅 U 型碗底翻揚系統 (20260703 究極嚴選版)***
    優化重點：
    1. 雙扣抵容許區間 ➡️ 留下華碩，洗掉結構不穩股。
    2. 均線發散度限制 ➡️ 洗掉短線暴衝、均線拉太開的精銳與祥碩。
    """
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 1. 技術指標計算
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 基本位階與趨勢檢查
    is_below_ma240 = today['MA60'] < today['MA240']
    
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.01 
    
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    
    # 🌟 優化一：扣抵值智能容許過濾 (避免誤殺華碩)
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    ma60_deduct_change = (ma60_deduct_5d_later - ma60_deduct_today) / ma60_deduct_today if ma60_deduct_today > 0 else 0
    is_ma60_deduct_ok = ma60_deduct_change <= 0.015

    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220]
    ma240_deduct_change = (ma240_deduct_20d_later - ma240_deduct_today) / ma240_deduct_today if ma240_deduct_today > 0 else 0
    is_ma240_deduct_ok = ma240_deduct_change <= 0.02

    print(f"ma240_deduct_today: {ma240_deduct_today} | ma240_deduct_20d_later: {ma240_deduct_20d_later} | ma240_deduct_change: {ma240_deduct_change}")
    
    # 🌟 優化二：均線發散度過濾 (精銳、祥碩殺手)
    ma_list = [today['MA5'], today['MA10'], today['MA20']]
    ma_dispersion = (max(ma_list) - min(ma_list)) / today['MA20'] if today['MA20'] > 0 else 0
    is_ma_not_overheated = ma_dispersion <= 0.06  # 限制短中期均線乖離在 6% 以內

    # 3. 量能與觸發判定
    is_triggered = today['close'] > today['open']
    
    # 4. 綜合判定
    is_hit = (is_below_ma240 and is_ma240_stable and is_ma60_turning_up and 
              is_short_trend_bullish and is_triggered and 
              is_ma60_deduct_ok and is_ma240_deduct_ok and is_ma_not_overheated)

    print(f"Below240: {is_below_ma240} | Stable240: {is_ma240_stable} | MA60Up: {is_ma60_turning_up} | ShortBull: {is_short_trend_bullish} | Triggered: {is_triggered}")
    print(f"ma60_deduct: {is_ma60_deduct_ok} | ma240_deduct: {is_ma240_deduct_ok} | not_overheated: {is_ma_not_overheated}")
    
    status = "[A-2 鑽石碗底] 均線溫和凝聚＋雙扣抵大吉！" if is_hit else "未觸發訊號"
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    info = {
        "收盤": today['close'],
        "均線發散度": f"{round(ma_dispersion * 100, 2)}%",
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "策略狀態": status
    }
        
    return is_hit, info

def st_bottom_u_turn_2026070302(df_single):
    """
    ***st_bottom_u_turn_2026070302 策略 A-2：題材破滅 U 型碗底翻揚系統 (純結構動能＋中長線雙扣抵預報版)***

    【核心篩選條件 (同時滿足才觸發 is_hit)】
    1. 基底檢查：季線仍在年線下方 (60MA < 240MA)，定位長期底部。
    2. 年線減速：年線 5 日變動率 >= -1.0%，確認長線跌勢已開始減速走平。
    3. 中線轉折：季線扭轉向上 (今日 60MA > 昨日 60MA)。
    4. 趨勢成形：短中期均線展現標準多頭排列 (5MA > 10MA > 20MA > 60MA)。
    5. 安全點火：當日必須收紅K (收盤價 > 開盤價)。
    
    ※ 註：季線與年線的扣抵走勢預報僅作為操作輔助與狀態描述，不計入 is_hit 的硬性門檻。
    """

    # 確保資料量足夠計算 240MA (加上緩衝至少需 260 筆)
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 1. 計算核心技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 基底檢查：季線仍在年線下方
    is_below_ma240 = today['MA60'] < today['MA240']
    
    # 3. 年線減速檢查：限制 5 日變動率放寬至 1.0%
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.01 
    
    # 4. 中線定海神針：季線（60MA）扭轉向上
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    # 🌟 5-A. 季線未來 5 日扣抵值走勢預報 (看短期發動續航力)
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    if ma60_deduct_5d_later < ma60_deduct_today:
        ma60_forecast = "輕鬆助漲 (扣抵走低)"
    else:
        ma60_forecast = "壓力引力 (扣抵走高)"

    # 🌟 5-B. 新增：年線未來 20 日 (一個月) 扣抵值走勢預報 (看大結構轉骨潛力)
    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220] # 20天後扣抵的位置
    if ma240_deduct_20d_later < ma240_deduct_today:
        ma240_forecast = "🔥 大吉！一年前股價正崩盤溜滑梯，有利突破年線後「長線轉骨」成主升段"
    else:
        ma240_forecast = "⏳ 橫盤！一年前股價在高檔死盤，年線下彎引力仍重，過年線後震盪難免"

    # 6. 趨勢成形：短中期均線在年線下方展現標準多頭排列
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    
    # 7. 【安全保險絲】當日必須收紅K
    is_triggered = today['close'] > today['open']
    
    # 計算量能比例（純資訊描述）
    vol_ratio = today['Trading_Volume'] / today['Vol_MA5'] if today['Vol_MA5'] > 0 else 0
    is_vol_type_A = vol_ratio >= 1.5
    is_vol_type_B = (today['Trading_Volume'] > yesterday['Trading_Volume']) and (today['Trading_Volume'] > today['Vol_MA5'])
    
    vol_style = "無量空漲 / 籌碼真空"
    if is_vol_type_A and is_vol_type_B:
        vol_style = "雙重觸發【暴發攻擊量】與【溫和遞增量】"
    elif is_vol_type_A:
        vol_style = "型態 A：底部暴發攻擊量(>=1.5x)"
    elif is_vol_type_B:
        vol_style = "型態 B：溫和放量遞增"
    
    # 8. 綜合獨立判定
    is_hit = is_below_ma240 and is_ma240_stable and is_ma60_turning_up and is_short_trend_bullish and is_triggered
    status = f"[A-2 碗底翻揚] 季線轉正＋均線小多頭！紅K點火確認 ({vol_style})" if is_hit else "未觸發訊號"
    
    # 9. 計算與年線的距離並產生操作策略建議
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    if dist_ratio < -0.05:
        action_strategy = "地下室反彈，年線附近停利"
    elif dist_ratio <= 0:
        action_strategy = "決戰天花板，注意年線反壓"
    else:
        action_strategy = "破繭而出，站穩年線看長線"
        
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線5日變動": f"{round(ma240_slope_5d * 100, 2)}%",
        "季線趨勢": f"翻揚向上 ({ma60_forecast})",
        "長線年線扣抵預報": ma240_forecast,  # 新增年線大預報
        "今日量比": f"{round(vol_ratio, 2)}x",
        "策略操作": action_strategy,
        "策略狀態": status
    }
    
    if is_hit:
        print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
        
    return is_hit, info

def st_bottom_u_turn_v2026070301(df_single):
    """
    ***st_bottom_u_turn_v2026070301 策略 A-2：題材破滅 U 型碗底翻揚系統 (雙扣抵結構硬過濾版)***
    
    核心邏輯：
    1. 位階限制：季線（60MA）在年線（240MA）下方，確保整體大結構處於低檔沉澱。
    2. 長線賣壓鈍化：年線下彎力道減速（5日內變動率 > -1.0%）。
    3. 靈魂解套訊號：季線（60MA）扭轉向上。
    4. 季線扣抵過濾：未來 5 日扣抵值必須走低，確保季線翻揚具備強力「結構性助漲」續航力。
    5. 年線扣抵過濾：未來 20 日扣抵值必須走低，確保上方年線魔王賣壓已實質減輕，利於長線轉骨。
    6. 小多頭排列：短期與中期均線整齊發散（5MA > 10MA > 20MA > 60MA）。
    7. 紅K保險絲：當日必須收紅K（Close > Open）。
    """
    # 確保資料量足夠計算 240MA (加上緩衝至少需 260 筆)
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 1. 計算核心技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 基底檢查：季線仍在年線下方
    is_below_ma240 = today['MA60'] < today['MA240']
    
    # 3. 年線減速檢查：限制 5 日變動率放寬至 1.0%
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    is_ma240_stable = ma240_slope_5d >= -0.01 
    
    # 4. 中線定海神針：季線（60MA）扭轉向上
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    # 🌟 5-A. 【硬過濾一】季線未來 5 日扣抵值必須走低 (拒絕硬拔的虛胖轉正)
    ma60_deduct_today = df_single['close'].iloc[-60]
    ma60_deduct_5d_later = df_single['close'].iloc[-55]
    is_ma60_deduct_ok = ma60_deduct_5d_later < ma60_deduct_today

    # 🌟 5-B. 【硬過濾二】年線未來 20 日扣抵值必須走低 (確保年線引力減輕，有利大波段)
    ma240_deduct_today = df_single['close'].iloc[-240]
    ma240_deduct_20d_later = df_single['close'].iloc[-220]
    is_ma240_deduct_ok = ma240_deduct_20d_later < ma240_deduct_today

    # 6. 趨勢成形：短中期均線在年線下方展現標準多頭排列
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    
    # 7. 【安全保險絲】當日必須收紅K
    is_triggered = today['close'] > today['open']
    
    # 計算量能比例（純資訊描述）
    vol_ratio = today['Trading_Volume'] / today['Vol_MA5'] if today['Vol_MA5'] > 0 else 0
    is_vol_type_A = vol_ratio >= 1.5
    is_vol_type_B = (today['Trading_Volume'] > yesterday['Trading_Volume']) and (today['Trading_Volume'] > today['Vol_MA5'])
    
    vol_style = "無量空漲 / 籌碼真空"
    if is_vol_type_A and is_vol_type_B:
        vol_style = "雙重觸發【暴發攻擊量】與【溫和遞增量】"
    elif is_vol_type_A:
        vol_style = "型態 A：底部暴發攻擊量(>=1.5x)"
    elif is_vol_type_B:
        vol_style = "型態 B：溫和放量遞增"
    
    # 🌟 8. 綜合獨立判定 (正式加入雙扣抵值過濾條件)
    is_hit = (is_below_ma240 and is_ma240_stable and is_ma60_turning_up and 
              is_short_trend_bullish and is_triggered and 
              is_ma60_deduct_ok and is_ma240_deduct_ok)
              
    status = f"[A-2 嚴選碗底] 雙扣抵大吉＋季線轉正！最強轉骨起漲點 ({vol_style})" if is_hit else "未觸發訊號"
    
    # 9. 計算與年線的距離並產生操作策略建議
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    if dist_ratio < -0.05:
        action_strategy = "地下室反彈，年線附近停利"
    elif dist_ratio <= 0:
        action_strategy = "決戰天花板，注意年線反壓"
    else:
        action_strategy = "破繭而出，站穩年線看長線"
        
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線5日變動": f"{round(ma240_slope_5d * 100, 2)}%",
        "季線趨勢": "翻揚向上 (結構助漲)" if is_ma60_turning_up else "依舊下彎",
        "今日量比": f"{round(vol_ratio, 2)}x",
        "策略操作": action_strategy,
        "策略狀態": status
    }
    
    if is_hit:
        print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
        
    return is_hit, info

def st_bottom_u_turn_v20260703(df_single):
    """
    ***st_bottom_u_turn_v20260703 策略 A-2：題材破滅 U 型碗底翻揚系統 ***
    
    核心邏輯：
    1. 位階限制：季線（60MA）在年線（240MA）下方，確保整體大結構處於低檔沉澱，並允許當日股價強勢穿透年線。
    2. 長線賣壓鈍化：年線下彎力道大幅減速（5日內變動率 > -0.5%），排除剛崩盤下墜的股票。
    3. 靈魂解套訊號：季線（60MA）扭轉向上，代表過去一整個季度的低檔換手盤正式轉為多頭贏家。
    4. 小多頭排列：短期與中期均線整齊發散（5MA > 10MA > 20MA > 60MA），右側攻擊動能成形。
    """
    # 確保資料量足夠計算 240MA (加上緩衝至少需 260 筆)
    if df_single.empty or len(df_single) < 260:
        return False, {}

    # 1. 計算核心技術指標
    df_single['MA5'] = df_single['close'].rolling(5).mean()
    df_single['MA10'] = df_single['close'].rolling(10).mean()
    df_single['MA20'] = df_single['close'].rolling(20).mean()
    df_single['MA60'] = df_single['close'].rolling(60).mean()
    df_single['MA240'] = df_single['close'].rolling(240).mean()
    df_single['Vol_MA5'] = df_single['Trading_Volume'].rolling(5).mean()
    
    today = df_single.iloc[-1]
    yesterday = df_single.iloc[-2]
    
    # 2. 基底檢查：季線仍在年線下方，確保人在地下室，允許今日收盤衝過年線
    is_below_ma240 = today['MA60'] < today['MA240']
    
    # 3. 年線減速檢查：限制 5 日變動率，確保年線已高度走緩，拒絕急墜股
    ma240_5d_ago = df_single['MA240'].iloc[-6]
    ma240_slope_5d = (today['MA240'] - ma240_5d_ago) / ma240_5d_ago if ma240_5d_ago > 0 else 0
    #is_ma240_stable = ma240_slope_5d >= -0.005  # 5天內下彎不超過 0.5%

    is_ma240_stable = ma240_slope_5d >= -0.01  # 5天內下彎不超過 0.5%
    
    # 4. 【核心靈魂】中線定海神針：季線（60MA）必須止跌翻揚轉向向上
    is_ma60_turning_up = today['MA60'] > yesterday['MA60']
    
    # 5. 趨勢成形：短中期均線在年線下方展現標準多頭排列
    is_short_trend_bullish = today['MA5'] > today['MA10'] > today['MA20'] > today['MA60']
    print(f"today['MA5']: {today['MA5']} | today['MA10']: {today['MA10']} | today['MA20']: {today['MA20']} | today['MA60']: {today['MA60']} ")

    
    # 6. 右側發動表態：量能雙軌判定
    vol_ratio = today['Trading_Volume'] / today['Vol_MA5'] if today['Vol_MA5'] > 0 else 0
    
    is_vol_type_A = vol_ratio >= 1.5
    is_vol_type_B = (today['Trading_Volume'] > yesterday['Trading_Volume']) and (today['Trading_Volume'] > today['Vol_MA5'])
    
    is_volume_ok = is_vol_type_A or is_vol_type_B
    #is_triggered = today['close'] > today['open'] and is_volume_ok
    is_triggered = today['close'] > today['open']
    
    # 詳細型態文字描述
    vol_style = "未放量"
    if is_vol_type_A and is_vol_type_B:
        vol_style = "雙重觸發【暴發攻擊量】與【溫和遞增量】"
    elif is_vol_type_A:
        vol_style = "型態 A：底部暴發攻擊量(>=1.5x)"
    elif is_vol_type_B:
        vol_style = "型態 B：溫和放量遞增"

    print(f"Below240: {is_below_ma240} | Stable240: {is_ma240_stable} | MA60Up: {is_ma60_turning_up} | ShortBull: {is_short_trend_bullish} | Triggered: {is_triggered}")
    
    # 7. 綜合獨立判定
    is_hit = is_below_ma240 and is_ma240_stable and is_ma60_turning_up and is_short_trend_bullish and is_triggered
    status = f"[A-2 碗底翻揚] 季線轉正＋均線小多頭！人在年線下安全伏擊點火 ({vol_style})" if is_hit else "未觸發訊號"
    
    # 8. 計算與年線的距離並動態產生簡單的操作策略建議
    dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    if dist_ratio < -0.05:
        action_strategy = "地下室反彈，年線附近停利"
    elif dist_ratio <= 0:
        action_strategy = "決戰天花板，注意年線反壓"
    else:
        action_strategy = "破繭而出，站穩年線看長線"
        
    info = {
        "收盤": today['close'],
        "距離年線": f"{round(dist_ratio * 100, 2)}%",
        "年線5日變動": f"{round(ma240_slope_5d * 100, 2)}%",
        "季線趨勢": "翻揚向上" if is_ma60_turning_up else "依舊下彎",
        "今日量比": f"{round(vol_ratio, 2)}x",
        "策略操作": action_strategy,  # 新增此欄位
        "策略狀態": status
    }
    
    #if is_hit:
    #   print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
    print(f"st_bottom_u_turn is_hit:{is_hit} info:{info}")
        
    return is_hit, info
