#strategy/engine.py
#回測策略引擎
import inspect
import pandas as pd
import numpy as np
from strategy.config import BUY_PARAM_PROFILES
from scipy.stats import linregress

def _preprocess_technical_indicators(df_single: pd.DataFrame) -> pd.DataFrame:
  """內部輔助函式：針對 FinMind 格式計算技術指標（正宗錢塘潮輕鬆線）、20日均量與成交金額"""
  if df_single is None or df_single.empty:
    return df_single

  df = df_single.copy()

  # =========================================================================
  # 1. 輕鬆線指標計算（更新為錢塘潮正宗演算法）
  # =========================================================================
  # 計算加權價格 Typical Price (FinMind 的最高價為 'max'，最低價為 'min')
  price_weighted = (df['max'] + df['min'] + df['close'] * 2) / 4

  # (1) 輕鬆 B (easy_buy): 短線攻擊快線 - 加權價格 6 EMA
  df['easy_buy'] = price_weighted.ewm(span=6, adjust=False).mean()

  # (2) 輕鬆 S (easy_sell): 長線確認慢線 - 加權價格 24 EMA
  df['easy_sell'] = price_weighted.ewm(span=24, adjust=False).mean()

  # (3) 輕鬆線 (easy_line): 主趨勢濾網線 - 收盤價 12/6 二次平滑 (Double EMA)
  ema_12 = df['close'].ewm(span=12, adjust=False).mean()
  df['easy_line'] = ema_12.ewm(span=6, adjust=False).mean()

  # =========================================================================
  # 2. 9日 KD 指標計算 (使用 FinMind 專用欄位：min / max)
  # =========================================================================
  low_min = df['min'].rolling(9).min()
  high_max = df['max'].rolling(9).max()

  denom = high_max - low_min
  denom = denom.replace(0, np.nan)

  rsv = (df['close'] - low_min) / denom * 100
  rsv = rsv.fillna(50)  # 漲跌停無振幅時分母為 0，以 50 替代

  # 3. 符合台股標準 KD 遞迴算式 (1/3 平滑, adjust=False)
  df['K'] = rsv.ewm(com=2, adjust=False).mean()
  df['D'] = df['K'].ewm(com=2, adjust=False).mean()

  # =========================================================================
  # 4. 第二類策略專用：20日均量與成交金額防線 (使用 FinMind 的 Trading_Volume)
  # =========================================================================
  df['volume_20_ma'] = df['Trading_Volume'].rolling(20).mean()

  # 計算成交金額（若 FinMind 每日股價沒有直接給 amount，用 close * Trading_Volume 計算）
  df['trading_amount'] = df['close'] * df['Trading_Volume']

  # =========================================================================
  # 5. 計算單筆均張 (SPT = (Trading_Volume / 1000) / Trading_turnover)
  # =========================================================================
  if 'Trading_Volume' in df.columns and 'Trading_turnover' in df.columns:
    # 防呆：避免成交筆數為 0 導致除以零
    turnover_safe = df['Trading_turnover'].replace(0, np.nan)
    df['shares_per_trans'] = (df['Trading_Volume'] / 1000) / turnover_safe
    df['shares_per_trans'] = df['shares_per_trans'].fillna(0)

  # =========================================================================
  # 6. 指數移動平均線計算 (EMA5, EMA10, EMA20, EMA60, EMA120, EMA240)
  # =========================================================================
  df['EMA5'] = df['close'].ewm(span=5, adjust=False).mean()
  df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
  df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
  df['EMA60'] = df['close'].ewm(span=60, adjust=False).mean()
  df['EMA120'] = df['close'].ewm(span=120, adjust=False).mean()
  df['EMA240'] = df['close'].ewm(span=240, adjust=False).mean()

  # =========================================================================
  # 7. 長線回測新增評估指標 (全數附加於原始程式後方)
  # =========================================================================
  # (1) 輕鬆線動能：乖離率(%) 與 5日 OLS 斜率
  df['easy_line_bias'] = (
      (df['close'] - df['easy_line']) / df['easy_line']
  ) * 100

  def _calc_slope_5(series):
    if len(series) < 5 or series.isna().any():
      return 0.0
    x = np.arange(len(series))
    res = linregress(x, series.values)
    return res.slope

  df['easy_line_slope'] = (
      df['easy_line']
      .rolling(window=5, min_periods=5)
      .apply(_calc_slope_5, raw=False)
  )

  # (2) 簡單移動平均線 (SMA: MA5, MA10, MA20, MA60, MA120, MA240)
  df['MA5'] = df['close'].rolling(window=5, min_periods=1).mean()
  df['MA10'] = df['close'].rolling(window=10, min_periods=1).mean()
  df['MA20'] = df['close'].rolling(window=20, min_periods=1).mean()
  df['MA60'] = df['close'].rolling(window=60, min_periods=1).mean()
  df['MA120'] = df['close'].rolling(window=120, min_periods=1).mean()
  df['MA240'] = df['close'].rolling(window=240, min_periods=1).mean()

  # 季線與年線乖離率 (%)
  df['ma60_bias'] = ((df['close'] - df['MA60']) / df['MA60']) * 100
  df['ma240_bias'] = ((df['close'] - df['MA240']) / df['MA240']) * 100

  # 計算 MA60 與 MA240 近 20 日 OLS 斜率
  def _calc_slope_20(series):
    if len(series) < 20 or series.isna().any():
      return 0.0
    x = np.arange(len(series))
    res = linregress(x, series.values)
    return res.slope

  df['ma60_slope'] = (
      df['MA60']
      .rolling(window=20, min_periods=20)
      .apply(_calc_slope_20, raw=False)
  )
  df['ma240_slope'] = (
      df['MA240']
      .rolling(window=20, min_periods=20)
      .apply(_calc_slope_20, raw=False)
  )

  # 季線 (MA60) 與年線 (MA240) 扣抵位置 % [(目前收盤價 - 扣抵價) / 扣抵價 * 100]
  close_shift60 = df['close'].shift(60)
  close_shift240 = df['close'].shift(240)
  df['ma60_deduct_bias'] = (
      (df['close'] - close_shift60) / close_shift60
  ) * 100
  df['ma240_deduct_bias'] = (
      (df['close'] - close_shift240) / close_shift240
  ) * 100

  # 均線多頭排列布林標記 (MA5 > MA20 > MA60 > MA240)
  df['is_bull_alignment'] = (
      (df['MA5'] > df['MA20'])
      & (df['MA20'] > df['MA60'])
      & (df['MA60'] > df['MA240'])
  )

  # 均線糾結度 (MA5, MA20, MA60, MA240 標準差 / 均值 %)
  ma_matrix = df[['MA5', 'MA20', 'MA60', 'MA240']]
  ma_std = ma_matrix.std(axis=1)
  ma_mean = ma_matrix.mean(axis=1)
  df['ma_tangle_ratio'] = (ma_std / ma_mean) * 100

  # (3) 觸發當日 K 線型態特徵 (純 FinMind 標準欄位: open, max, min, close)
  high_low_range = (df['max'] - df['min']).replace(0, np.nan)
  body = (df['close'] - df['open']).abs()
  upper_shadow = df['max'] - df[['open', 'close']].max(axis=1)

  df['body_ratio'] = ((body / high_low_range) * 100.0).fillna(0.0)
  df['upper_shadow_ratio'] = ((upper_shadow / high_low_range) * 100.0).fillna(0.0)
  df['is_red_k'] = df['close'] >= df['open']
  
  # (4) 成交量能與金額擴充
  df['vol_ma5'] = df['Trading_Volume'].rolling(5).mean()
  df['amount_100m'] = df['trading_amount'] / 100000000.0

  # (5) 長線 52 週 (240日) 位階與打底沉澱天數
  df['high_52w'] = df['max'].rolling(window=240, min_periods=30).max()
  df['low_52w'] = df['min'].rolling(window=240, min_periods=30).min()
  df['dist_to_52w_high_pct'] = (
      (df['close'] - df['high_52w']) / df['high_52w']
  ) * 100

  # 打底沉澱天數：近 60 日內，收盤價在輕鬆線 ±5% 範圍內的總天數
  in_consolidation = (df['close'] >= df['easy_line'] * 0.95) & (
      df['close'] <= df['easy_line'] * 1.05
  )
  df['base_consolidation_days'] = (
      in_consolidation.astype(int).rolling(window=60, min_periods=1).sum()
  )

  # =========================================================================
  # 7. 三大法人與信用交易籌碼預處理 (極簡防衛架構, 直接採用 FinMind 原生欄位，單位: 股)
  # =========================================================================
  # 1. 三大法人 (流量)：先補 0.0 再計算近 5 日滾動累計 (單位: 股)
  if "Foreign_Investor" in df.columns:
    df["foreign_5d_shares_sum"] = (
      df["Foreign_Investor"].fillna(0.0).rolling(5, min_periods=1).sum()
    )
    df["trust_5d_shares_sum"] = (
      df["Investment_Trust"].fillna(0.0).rolling(5, min_periods=1).sum()
    )
    df["major_5d_shares_sum"] = (
      df["major_net"].fillna(0.0).rolling(5, min_periods=1).sum()
    )

  # 2. 融資融券 (存量)：先 ffill 避開單日 API 漏抓陷阱，再補 0.0 (單位: 張)  
  if "MarginPurchaseTodayBalance" in df.columns:
    df["MarginPurchaseTodayBalance"] = (
      df["MarginPurchaseTodayBalance"].ffill().fillna(0.0)
    )
    df["ShortSaleTodayBalance"] = (
      df["ShortSaleTodayBalance"].ffill().fillna(0.0)
    )

  # 3. 計算當日增減 (單位: 張，不會產生假的 -5000 張爆砍訊號)
  df["margin_diff_shares"] = (
      df["MarginPurchaseTodayBalance"].diff().fillna(0.0)
  )
  df["short_diff_shares"] = df["ShortSaleTodayBalance"].diff().fillna(0.0)

  # 🌟 新增：全量計算 MACD (12, 26, 9) 指標
  exp1 = df['close'].ewm(span=12, adjust=False).mean()
  exp2 = df['close'].ewm(span=26, adjust=False).mean()
  df['dif'] = exp1 - exp2
  df['dem'] = df['dif'].ewm(span=9, adjust=False).mean()
  df['osc'] = (df['dif'] - df['dem']) * 2.0  # MACD 柱狀體
    
  return df

def preprocess_all_technical_indicators(global_df: pd.DataFrame) -> pd.DataFrame:
    """
    【全域預處理入口】資料抓取完成後呼叫，一次性預先算好所有股票的技術指標 (KD, 輕鬆線, 20日均量, 成交金額)
    """
    if global_df.empty:
        return global_df

    processed_dfs = []
    # 確保以 FinMind 的 stock_id 進行群組與排序
    for sid, group_df in global_df.groupby('stock_id'):
        sorted_group = group_df.sort_values('date').copy()
        processed_group = _preprocess_technical_indicators(sorted_group)
        processed_dfs.append(processed_group)

    return pd.concat(processed_dfs, ignore_index=True)

def scan_single_stock(
    df_single: pd.DataFrame,
    category: str,
    func_list: list,
    param_profiles: dict = BUY_PARAM_PROFILES,
    market_info: dict = None
) -> list:
    """
    【核心底層】單一股票的監控策略檢測元件
    預設輸入的 df_single 已經過全域預處理（含技術指標）
    """
    if len(df_single) < 5:
        return []

    category = str(category).strip()
    if category not in param_profiles:
        raise ValueError(
            f"❌ [設定檔錯誤] 類別 '{category}' 未定義於 PARAM_PROFILES 中！\n"
            f"可用的類別有：{list(param_profiles.keys())}"
        )

    profile = param_profiles[category].copy()
    profile['category'] = category

    hits = []
    for run_func in func_list:
        sig_params = inspect.signature(run_func).parameters
        
        if 'profile' in sig_params:
            is_hit, info = run_func(df_single, profile=profile)
        else if 'market_info' in sig_params:
            is_hit, info = run_func(df_single, market_info=market_info)      
        else:
            is_hit, info = run_func(df_single, market_info=market_info)

        if is_hit:
            res_info = info if isinstance(info, dict) else {"detail": str(info)}
            res_info["strategy_name"] = run_func.__name__
            res_info["category"] = category
            hits.append(res_info)

    return hits

