#utils/indicators.py
import numpy as np
import pandas as pd

def _preprocess_technical_indicators(df_single: pd.DataFrame) -> pd.DataFrame:
    """內部輔助函式：針對 FinMind 格式計算通用技術指標

    包含：正宗錢塘潮輕鬆線 (easy_buy, easy_sell, easy_line)、9日KD (K, D)、
    5/20日均量 (volume_5_ma, volume_20_ma)、每筆成交股數 (shares_per_trans) 與成交金額 (trading_amount)
    """
    if df_single is None or df_single.empty:
        return df_single

    df = df_single.copy()

    # =========================================================================
    # 1. 輕鬆線指標計算（錢塘潮正宗演算法）
    # =========================================================================
    # FinMind 最高價為 'max'，最低價為 'min'
    price_weighted = (df["max"] + df["min"] + df["close"] * 2) / 4
    df["easy_buy"] = price_weighted.ewm(span=6, adjust=False).mean()
    df["easy_sell"] = price_weighted.ewm(span=24, adjust=False).mean()

    ema_12 = df["close"].ewm(span=12, adjust=False).mean()
    df["easy_line"] = ema_12.ewm(span=6, adjust=False).mean()

    # =========================================================================
    # 2. 9日 KD 指標計算 (使用 FinMind 專用欄位：min / max)
    # =========================================================================
    low_min = df["min"].rolling(9).min()
    high_max = df["max"].rolling(9).max()

    denom = (high_max - low_min).replace(0, np.nan)
    rsv = ((df["close"] - low_min) / denom * 100).fillna(50)

    df["K"] = rsv.ewm(com=2, adjust=False).mean()
    df["D"] = df["K"].ewm(com=2, adjust=False).mean()

    # =========================================================================
    # 3. 均量與成交資訊計算
    # =========================================================================
    df["volume_5_ma"] = df["Trading_Volume"].rolling(5).mean()
    df["volume_20_ma"] = df["Trading_Volume"].rolling(20).mean()

    # 每筆成交股數 (Trading_Volume / Trading_turnover)
    if "Trading_turnover" in df.columns:
        turnover_safe = df["Trading_turnover"].replace(0, np.nan)
        df["shares_per_trans"] = (df["Trading_Volume"] / turnover_safe).fillna(
            0.0
        )
    else:
        df["shares_per_trans"] = 0.0

    # 成交金額
    df["trading_amount"] = df["close"] * df["Trading_Volume"]

    return df


def preprocess_all_technical_indicators(
    global_df: pd.DataFrame,
) -> pd.DataFrame:
    """【全域預處理入口】專門為 FinMind 資料格式進行指標預處理"""
    if global_df is None or global_df.empty:
        return global_df

    processed_dfs = []
    # 直接以 FinMind 的 stock_id 分組
    for sid, group_df in global_df.groupby("stock_id"):
        sorted_group = group_df.sort_values("date").copy()
        processed_group = _preprocess_technical_indicators(sorted_group)
        processed_dfs.append(processed_group)

    return pd.concat(processed_dfs, ignore_index=True)
