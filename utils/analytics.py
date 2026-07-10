# utils/analytics.py
import pandas as pd

def calculate_one_year_extremes(stock_id, trigger_date_str, global_df):
    """
    【區間波段效能追蹤】計算特定股票在觸發日期之後，一年內(240個交易日)的最高與最低績效
    """
    # 篩選出該檔股票的所有歷史資料，並依日期排序
    df_stock = global_df[global_df['stock_id'] == stock_id].sort_values('date').reset_index(drop=True)
    
    if df_stock.empty:
        return {}
    
    # 找到觸發當日在 DataFrame 中的索引位置
    trigger_idx_list = df_stock[df_stock['date'] <= trigger_date_str].index
    if len(trigger_idx_list) == 0:
        return {}
    
    trigger_idx = trigger_idx_list[-1]
    entry_price = df_stock.loc[trigger_idx, 'close']  # 進場價（觸發當日收盤價）
    
    # 定義未來一年（約 240 個交易日）的資料切片區間
    start_future_idx = trigger_idx + 1
    end_future_idx = trigger_idx + 240
    
    # 擷取未來的資料片段
    df_future = df_stock.iloc[start_future_idx : end_future_idx + 1]
    
    perf_results = {}
    
    if df_future.empty:
        perf_results["1Y內最高績效"] = "資料不足 (無未來資料)"
        perf_results["1Y內最低績效"] = "資料不足 (無未來資料)"
        return perf_results

    # 1. 尋找一年內的最高價與發生日期
    max_row = df_future.loc[df_future['close'].idxmax()]
    max_price = max_row['close']
    max_date = max_row['date']
    max_return = ((max_price - entry_price) / entry_price) * 100
    
    # 2. 尋找一年內的最低價與發生日期
    min_row = df_future.loc[df_future['close'].idxmin()]
    min_price = min_row['close']
    min_date = min_row['date']
    min_return = ((min_price - entry_price) / entry_price) * 100
    
    # 3. 標註資料是否足滿一年 (不滿 240 天會加上警示，方便你在 CSV 閱讀)
    status_suffix = "" if len(df_future) >= 240 else " (未滿1年)"
    
    perf_results["1Y內最高績效"] = f"{round(max_return, 2)}% ({max_date}){status_suffix}"
    perf_results["1Y內最低績效"] = f"{round(min_return, 2)}% ({min_date}){status_suffix}"
    
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
