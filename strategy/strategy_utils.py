import numpy as np


def check_recent_gap(df_subset):
  """檢測傳入的成交紀錄片段（如最近 5 天）內是否有跳空缺口

  :param df_subset: 包含 'high', 'low' 的 DataFrame 片段（需包含前一天以供比對）
  :return: bool (是否有跳空缺口)
  """
  if df_subset.empty or len(df_subset) < 2:
    return False

  prev_high = df_subset['high'].shift(1)
  # 標準真跳空：當日最低價大於昨日最高價
  has_gap_up = (df_subset['low'] > prev_high).any()
  return bool(has_gap_up)


def check_recent_volume_shrink(df_subset, shrink_ratio=0.7):
  """檢測傳入的成交紀錄片段（如最近 5 天）內是否有明顯量縮

  :param df_subset: 包含 'Trading_Volume' 的 DataFrame 片段
  :param shrink_ratio: 量縮門檻（例如成交量低於 20 日均量的 70%）
  :return: tuple (has_shrink, min_volume_ratio)
  """
  if df_subset.empty:
    return False, 0.0

  if 'volume_ma20' in df_subset.columns:
    vol_ma20 = df_subset['volume_ma20']
  else:
    vol_ma20 = df_subset['Trading_Volume'].rolling(20).mean()

  # 計算最近片段內的量比 (當日量 / 20日均量)
  vol_ratios = df_subset['Trading_Volume'] / vol_ma20
  vol_ratios = vol_ratios.replace([np.inf, -np.inf], np.nan).dropna()

  if vol_ratios.empty:
    return False, 0.0

  min_ratio = vol_ratios.min()
  has_shrink = (vol_ratios < shrink_ratio).any()

  return bool(has_shrink), round(float(min_ratio), 2)
