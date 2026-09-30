import inspect
import pandas as pd
import numpy as np
from strategy.config import BUY_PARAM_PROFILES

def scan_single_stock(
    df_single: pd.DataFrame,
    category: str,
    func_list: list,
    param_profiles: dict = BUY_PARAM_PROFILES
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
        else:
            is_hit, info = run_func(df_single)

        if is_hit:
            res_info = info if isinstance(info, dict) else {"detail": str(info)}
            res_info["strategy_name"] = monitor_func.__name__
            res_info["category"] = category
            hits.append(res_info)

    return hits

