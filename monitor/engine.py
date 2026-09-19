# monitor/engine.py
import inspect
import pandas as pd
from monitor.config import PARAM_PROFILES      # <-- 這裡改為從 config 匯入
from monitor.registry import ACTIVE_MONITORS

def scan_sell_signals(
    portfolio_df: pd.DataFrame,
    all_df: pd.DataFrame,
    monitor_list: list = None,
    param_profiles: dict = PARAM_PROFILES
) -> list:
    # ...引擎主體邏輯維持不變...
