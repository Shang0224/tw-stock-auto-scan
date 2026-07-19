# utils/analytics.py
import pandas as pd

def calculate_one_year_extremes(stock_id, trigger_date_str, global_df):
    """
    【區間極值績效】計算特定股票在觸發日期之後，一年內(240個交易日)的最高與最低績效。
    並透過特殊符號標註時序：先發生的日期用 $$ 框住，後發生的日期用 () 框住。
    """
    df_stock = global_df[global_df['stock_id'] == stock_id].sort_values('date').reset_index(drop=True)
    if df_stock.empty: return {}
    
    trigger_idx_list = df_stock[df_stock['date'] <= trigger_date_str].index
    if len(trigger_idx_list) == 0: return {}
    
    trigger_idx = trigger_idx_list[-1]
    entry_price = df_stock.loc[trigger_idx, 'close']
    
    # 擷取未來一年（240個交易日）的資料
    df_future = df_stock.iloc[trigger_idx + 1 : trigger_idx + 241]
    perf_results = {}
    
    if df_future.empty:
        perf_results["1Y內最高績效"] = "資料不足"
        perf_results["1Y內最低績效"] = "資料不足"
        return perf_results

    # 1. 找出最高與最低價的資料列與索引
    max_idx = df_future['close'].idxmax()
    min_idx = df_future['close'].idxmin()
    
    max_row = df_future.loc[max_idx]
    min_row = df_future.loc[min_idx]
    
    max_date = max_row['date']
    min_date = min_row['date']
    
    max_return = ((max_row['close'] - entry_price) / entry_price) * 100
    min_return = ((min_row['close'] - entry_price) / entry_price) * 100

    print(f"{stock_id} ---min_date : {min_date} | min_row : {min_row['close']} | entry_price : {entry_price}-----------")
    
    # 2. 時序判定：比較 index 來決定誰先發生
    if max_idx < min_idx:
        # 最高價先發生
        max_date_fmt = f"$${max_date}$$"
        min_date_fmt = f"({min_date})"
    elif min_idx < max_idx:
        # 最低價先發生
        max_date_fmt = f"({max_date})"
        min_date_fmt = f"$${min_date}$$"
    else:
        # 同一天發生（通常是 df_future 只有一筆資料）
        max_date_fmt = f"({max_date})"
        min_date_fmt = f"({min_date})"
        
    status_suffix = "" if len(df_future) >= 240 else " (未滿1年)"
    
    # 3. 組合輸出結果
    perf_results["1Y內最高績效"] = f"{round(max_return, 2)}% {max_date_fmt}{status_suffix}"
    perf_results["1Y內最低績效"] = f"{round(min_return, 2)}% {min_date_fmt}{status_suffix}"
    
    return perf_results


def calculate_fixed_horizon_returns(stock_id, trigger_date_str, global_df):
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
