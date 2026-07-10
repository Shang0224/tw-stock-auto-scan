# utils/analytics.py
import pandas as pd

def calculate_forward_performance(stock_id, trigger_date_str, global_df):
    """
    【績效回測工具】計算特定股票在觸發日期之後 1M, 3M, 6M, 1Y 的實質績效
    """
    df_stock = global_df[global_df['stock_id'] == stock_id].sort_values('date').reset_index(drop=True)
    
    if df_stock.empty:
        return {}
    
    # 找到觸發當日在 DataFrame 中的索引位置
    trigger_idx_list = df_stock[df_stock['date'] <= trigger_date_str].index
    if len(trigger_idx_list) == 0:
        return {}
    
    trigger_idx = trigger_idx_list[-1]
    entry_price = df_stock.loc[trigger_idx, 'close']
    
    perf_results = {}
    # 交易日跨度估算 (1M=20天, 3M=60天, 6M=120天, 1Y=240天)
    horizons = {
        "1M後績效": 20,
        "3M後績效": 60,
        "6M後績效": 120,
        "1Y後績效": 240
    }
    
    for label, offset in horizons.items():
        target_idx = trigger_idx + offset
        if target_idx < len(df_stock):
            future_price = df_stock.loc[target_idx, 'close']
            future_date = df_stock.loc[target_idx, 'date']
            return_rate = ((future_price - entry_price) / entry_price) * 100
            perf_results[label] = f"{round(return_rate, 2)}% ({future_date})"
        else:
            perf_results[label] = "資料不足 (未滿期)"
            
    return perf_results
