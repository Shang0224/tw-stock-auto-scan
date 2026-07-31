import numpy as np
from scipy.stats import linregress

def calculate_ols_slope_and_r2(series):
  """計算任意時間序列（如均線）的 OLS 最小平方法迴歸斜率與 R平方擬合度

  :param series: 包含一段數值的 pandas Series
  :return: tuple (slope_pct, r_squared)
           - slope_pct: 每日百分比斜率化數值
           - r_squared: 擬合優度 (0~1)，愈接近 1 代表走勢愈平滑穩定
  """
  y = series.dropna().values
  if len(y) < 2:
    return 0.0, 0.0

  x = np.arange(len(y))
  slope, intercept, r_value, p_value, std_err = linregress(x, y)
  r_squared = r_value**2

  mean_val = np.mean(y)
  slope_pct = (slope / mean_val) * 100 if mean_val > 0 else 0

  return slope_pct, r_squared

def check_recent_gap(df_subset):
  """檢測傳入的成交紀錄片段（如最近 5 天）內是否有跳空缺口

  :param df_subset: 包含 'high', 'low' 的 DataFrame 片段（需包含前一天以供比對）
  :return: bool (是否有跳空缺口)
  """
  if df_subset.empty or len(df_subset) < 2:
    return False

  prev_high = df_subset['max'].shift(1)
  # 標準真跳空：當日最低價大於昨日最高價
  has_gap_up = (df_subset['min'] > prev_high).any()
  return bool(has_gap_up)

def check_volume_condition(df_subset, threshold=2.0, is_surge=True):
  """通用的成交量變化檢測函數（透過布林值切換爆量或量縮）

  :param df_subset: 包含 'Trading_Volume' 的 DataFrame 片段
  :param threshold: 判斷門檻（爆量預設 2.0 倍，量縮建議設為 0.7 倍等）
  :param is_surge: 布林值，True 為檢測爆量，False 為檢測量縮
  :return: tuple (is_triggered, target_ratio)
  """
  if df_subset.empty:
    return False, 0.0

  if 'volume_ma20' in df_subset.columns:
    vol_ma20 = df_subset['volume_ma20']
  else:
    vol_ma20 = df_subset['Trading_Volume'].rolling(20).mean()

  # 計算區間內的量比 (當日量 / 20日均量)
  vol_ratios = df_subset['Trading_Volume'] / vol_ma20
  vol_ratios = vol_ratios.replace([np.inf, -np.inf], np.nan).dropna()

  if vol_ratios.empty:
    return False, 0.0

  # 根據布林值決定邏輯
  if is_surge:
    target_ratio = vol_ratios.max()
    is_triggered = (vol_ratios >= threshold).any()
  else:
    target_ratio = vol_ratios.min()
    is_triggered = (vol_ratios <= threshold).any()

  return bool(is_triggered), round(float(target_ratio), 2)

  min_ratio = vol_ratios.min()
  has_shrink = (vol_ratios < shrink_ratio).any()

  return bool(has_shrink), round(float(min_ratio), 2)
