# monitor/engine.py
import inspect
import pandas as pd
import numpy as np
from monitor.config import PARAM_PROFILES

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
    low_min  = df['min'].rolling(9).min()
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


def scan_single_stock_monitors(
    df_single: pd.DataFrame,
    category: str,
    monitor_list: list,
    param_profiles: dict = PARAM_PROFILES
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
    for monitor_func in monitor_list:
        sig_params = inspect.signature(monitor_func).parameters
        
        if 'profile' in sig_params:
            is_hit, info = monitor_func(df_single, profile=profile)
        else:
            is_hit, info = monitor_func(df_single)

        if is_hit:
            res_info = info if isinstance(info, dict) else {"detail": str(info)}
            res_info["strategy_name"] = monitor_func.__name__
            res_info["category"] = category
            hits.append(res_info)

    return hits


def scan_sell_signals(
    portfolio_df: pd.DataFrame,
    all_df: pd.DataFrame,
    monitor_list: list = None,
    param_profiles: dict = PARAM_PROFILES
) -> list:
    """
    【持股賣訊掃描】專門處理實盤/廣播的持股比對與報酬率計算
    """
    if not monitor_list:
        raise ValueError("【錯誤】未指定 monitor_list 策略清單，請於呼叫端明確傳入！")

    if all_df is None or all_df.empty or portfolio_df is None or portfolio_df.empty:
        return []

    warnings = []
    grouped = all_df.groupby('stock_id')

    for idx, row in portfolio_df.iterrows():
        sid = str(row['stock_id'])
        sname = str(row.get('name', ''))
        cost_price = float(row.get('cost_price', 0)) if pd.notnull(row.get('cost_price')) else 0.0
        category = str(row.get('category', '')).strip()

        if sid not in grouped.groups:
            continue

        df_single = grouped.get_group(sid).sort_values('date').copy()
        
        # 呼叫單股檢測核心 (純粹進行策略觸發判定，不再重複算指標)
        hits = scan_single_stock_monitors(
            df_single=df_single,
            category=category,
            monitor_list=monitor_list,
            param_profiles=param_profiles
        )

        if hits:
            latest_close = float(df_single['close'].iloc[-1])
            return_pct_str = f"{((latest_close - cost_price) / cost_price) * 100:+.2f}%" if cost_price > 0 else "N/A"

            for info in hits:
                info['stock_id'] = sid
                info['stock_name'] = sname
                info['cost_price'] = cost_price if cost_price > 0 else 'N/A'
                info['close'] = latest_close
                info['return_pct'] = return_pct_str
                warnings.append(info)

    return warnings
