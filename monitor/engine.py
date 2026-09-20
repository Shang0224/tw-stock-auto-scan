# monitor/engine.py
import inspect
import pandas as pd
import numpy as np
from monitor.config import PARAM_PROFILES
from monitor.registry import ACTIVE_MONITORS


def _preprocess_technical_indicators(df_single: pd.DataFrame) -> pd.DataFrame:
    """內部輔助函式：預先計算 Monitor 所需之技術指標（輕鬆線、KD等）"""
    df = df_single.copy()
    
    # 輕鬆線指標計算
    df['easy_line'] = df['close'].rolling(20).mean()
    df['easy_b'] = df['close'].ewm(span=5).mean()
    df['easy_s'] = df['close'].ewm(span=20).mean()

    # 9日 KD 指標計算
    low_min = df['min'].rolling(9).min()
    high_max = df['max'].rolling(9).max()
    
    # 避免分母為 0 的極端情況
    denom = high_max - low_min
    denom = denom.replace(0, np.nan)
    rsv = (df['close'] - low_min) / denom * 100
    rsv = rsv.fillna(50)
    
    df['K'] = rsv.ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()

    return df


def scan_sell_signals(
    portfolio_df: pd.DataFrame,
    all_df: pd.DataFrame,
    monitor_list: list = None,
    param_profiles: dict = PARAM_PROFILES
) -> list:
    """
    持股賣訊掃描執行引擎
    
    Parameters:
        portfolio_df (pd.DataFrame): 使用者持股清單 (包含 stock_id, cost_price, profile 等欄位)
        all_df (pd.DataFrame): 包含歷史價量與籌碼之完整資料庫
        monitor_list (list, optional): 要執行的 Monitor 函數清單。若為 None，預設載入 ACTIVE_MONITORS。
        param_profiles (dict, optional): 族群參數對照表。預設載入 PARAM_PROFILES。
        
    Returns:
        list: 觸發警告的持股訊息清單
    """
    if monitor_list is None:
        monitor_list = ACTIVE_MONITORS

    if all_df is None or all_df.empty or portfolio_df is None or portfolio_df.empty:
        return []

    warnings = []
    grouped = all_df.groupby('stock_id')

    for idx, row in portfolio_df.iterrows():
        sid = str(row['stock_id'])
        sname = str(row.get('name', ''))
        
        # 成本價與當前報酬率計算
        cost_price = float(row.get('cost_price', 0)) if pd.notnull(row.get('cost_price')) else 0.0
        
        # 取得設定的族群 profile 參數
        profile_key = row.get('profile', 'default')
        profile = param_profiles.get(profile_key, param_profiles.get('default', {}))

        # 檢查該檔股票是否有歷史資料
        if sid not in grouped.groups:
            continue

        # 取出該股 K 線並排序
        df_single = grouped.get_group(sid).sort_values('date').copy()
        if len(df_single) < 5:
            continue

        # 計算必要的技術指標
        df_single = _preprocess_technical_indicators(df_single)

        # 取得最新收盤價與計算報酬率
        latest_close = float(df_single['close'].iloc[-1])
        if cost_price > 0:
            return_pct_val = ((latest_close - cost_price) / cost_price) * 100
            return_pct_str = f"{return_pct_val:+.2f}%"
        else:
            return_pct_str = "N/A"

        # 逐一執行啟用的 Monitor 檢測
        for monitor_func in monitor_list:
            sig_params = inspect.signature(monitor_func).parameters
            
            # 依據函數簽名選擇性傳入 profile 參數
            if 'profile' in sig_params:
                is_hit, info = monitor_func(df_single, profile=profile)
                print(f"profile : {profile}")
            else:
                is_hit, info = monitor_func(df_single)
                print("no profile")

            if is_hit:
                # 補全警報相關基礎資訊
                info['stock_id'] = sid
                info['stock_name'] = sname
                info['cost_price'] = cost_price if cost_price > 0 else 'N/A'
                info['close'] = latest_close
                info['return_pct'] = return_pct_str
                
                warnings.append(info)

    return warnings
