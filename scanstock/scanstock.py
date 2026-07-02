from FinMind.data import DataLoader
import pandas as pd
import time
from datetime import datetime, timedelta, timezone
import os
import requests

def scan_stocks_df_list(stock_ids, algo_func_list, all_df, stock_map):

    final_hits = []
    grouped = all_df.groupby('stock_id')

    for sid in stock_ids:

        if sid == "2385":
            print("群光-----------------------------------")
        
        if sid not in grouped.groups: continue
        df_single = grouped.get_group(sid).sort_values('date')
        
        # 初始標籤
        hit_row = {
            "代號": sid,
            "名稱": stock_map.get(sid, "未知"),
            "觸發策略": []
        }
        any_hit = False

        for algo_func in algo_func_list:
            
            is_hit, detail_info = algo_func(df_single=df_single)
            if is_hit:
                any_hit = True
                # 紀錄策略名稱
                hit_row["觸發策略"].append(algo_func.__doc__.strip().split('\n')[0])
                # 【關鍵】將詳細內容合併進這一列
                #print(f"{algo_func.__name__} - detail_info : {detail_info}")
                hit_row.update(detail_info)
        
        if any_hit:
            # 將串列轉為字串方便 CSV 儲存
            hit_row["觸發策略"] = "; ".join(hit_row["策略狀態"])
            hit_row["觸發策略"] = "; ".join(hit_row["策略狀態"])
            final_hits.append(hit_row)
            
    return final_hits



def scan_stocks_new(stock_ids, algo_func, dl):
    """
    通用策略執行器
    :param stock_ids: 股票代號串列 (List of Strings)
    :param strategy_func: 策略函數指標 (Function Pointer)
    :param dl: FinMind 或自定義的 DataLoader 物件
    :param days: 往前回推的天數
    :return: 所有命中策略的結果清單
    """
    # 1. 計算日期區間
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")

    print(f"🚀 [Batch] 開始抓取 {len(stock_ids)} 檔股票資料 (從 {start_date} 起)...")
    
    # 2. 一次性批次抓取 (這是效能關鍵)
    try:
        print("--- Data Info ---")
        all_df = dl.taiwan_stock_daily(stock_id=stock_ids, start_date=start_date, end_date=end_date)

        print("--- Debug Info ---")
        print(f"傳入的 ID 數量: {len(stock_ids)}")
        print(f"抓回來的總列數: {len(all_df)}")
        print(f"抓回來的股票清單: {all_df['stock_id'].unique()}")
        print("------------------")
    except Exception as e:
        print(f"❌ 批次抓取資料失敗: {e}")
        return []

    if all_df.empty:
        print("⚠️ 抓取結果為空，請檢查代號或網路。")
        return []

    # 3. 執行策略迴圈
    final_hits = []
    
    # 使用 groupby 可以更快速地在記憶體中拆分各檔股票
    grouped = all_df.groupby('stock_id')

    for sid in stock_ids:
        
        print(f"scan_stocks_new({sid}))")
        
        # 從 Grouped 物件中取出該檔股票的 Dataframe
        if sid not in grouped.groups:
            print(f"{sid} not in grouped.groups\n")           
            continue
            
        df_single = grouped.get_group(sid).sort_values('date')

        print(f"df_single({len(df_single)})")
        
        # 呼叫傳入的策略函數指標
        is_hit, info = algo_func(sid, df_single)
        
        if is_hit:
            final_hits.append(info)
            
    print(f"✅ 掃描完成，符合條件數: {len(final_hits)}")
    return final_hits


def scan_stocks(stock_ids, algo_func, dl):
    """
    通用掃描器：只負責傳入代號，不干涉策略細節
    """
    # 1. 先抓一次全市場基本資訊
    df_info = dl.taiwan_stock_info()

    print("df_info...\n")
    # 建立一個字典，方便快速查找名稱：{ "2317": "鴻海", ... }
    stock_name_dict = dict(zip(df_info['stock_id'], df_info['stock_name']))
    
    hits = []
    for sid in stock_ids:
        try:
            # 只需要把 sid 和 dl 丟進去，剩下的策略會自己搞定
            is_hit, info = algo_func(sid, dl, stock_name_dict)

            if is_hit:
                # 從傳進來的字典取得名稱
                #res = {"股票名稱": stock_name_dict.get(sid, "未知")}
                #res.update(info)
                #hits.append(res)
                hits.append(info)
                print(f"✅ 策略命中: {sid}")
            
            time.sleep(0.5) # 保護 API
        except Exception as e:
            print(f"❌ {sid} 處理出錯: {e}")
    return hits

def scan_stocks_df(stock_ids, algo_func, all_df, stock_map):
    """
    通用掃描器：只負責傳入代號，不干涉策略細節
    """

 
    hits = []
    for sid in stock_ids:
        try:          
            # 只需要把 df 丟進去，剩下的策略會自己搞定
            is_hit, info = algo_func(all_df)
            print(f"{sid} {stock_map.get(sid, '未知')} info: {info}")
            if is_hit:
                # 從傳進來的字典取得名稱
                stock_info = {"代號":sid, "股票名稱": stock_map.get(sid, "未知")}                
                res = {**stock_info, **info}
                hits.append(res)
                print(f"✅ 策略命中: {sid} --- res:{res}")
            
            time.sleep(0.5) # 保護 API
        except Exception as e:
            print(f"❌ {sid} 處理出錯: {e}")
    return hits
