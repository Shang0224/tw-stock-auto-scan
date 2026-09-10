# utils/data_fetcher.py
import os
import requests
import yfinance as yf
import pandas as pd
import time
from FinMind.data import DataLoader
from datetime import datetime, timedelta, timezone

def yf_fetch_monitor_stocks(monitor_stocks, days_before=365, days_after=548):
    """
    接收 monitor_stocks (字典列表)，針對每一筆資料的股票代號與觸發日期，
    自動計算「觸發日期前 days_before 天」到「觸發日期後 days_after 天」的交易資料並進行下載與合併。
    
    :param monitor_stocks: list, 包含股票代號與觸發日期的字典列表
    :param days_before: int, 觸發日期往前推的天數 (預設 365 天，即 1 年)
    :param days_after: int, 觸發日期往後推的天數 (預設 548 天，即約 1 年半)
    """
    all_data = []
    
    print(f"📡 準備處理共 {len(monitor_stocks)} 筆監控股票與觸發日期區間...")
    
    for idx, item in enumerate(monitor_stocks):
        sid = item['代號']
        trigger_date_str = item['觸發日期'] # 格式例如 '2020/5/14'
        
        # 1. 將觸發日期字串轉為 datetime 物件
        trigger_dt = datetime.strptime(trigger_date_str.replace('-', '/'), '%Y/%m/%d')
        
        # 2. 依照傳入的變數計算前後區間天數
        start_dt = trigger_dt - timedelta(days=days_before)
        end_dt = trigger_dt + timedelta(days=days_after)
        
        start_date = start_dt.strftime('%Y-%m-%d')
        # 因為 yfinance 結束日期不包含當天，故需將 end_date 再加 1 天
        end_date_plus_one = (end_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 3. 處理台股代號後綴
        if str(sid).startswith("^") or "." in str(sid):
            ticker_id = str(sid)
        else:
            ticker_id = f"{sid}.TW"
            
        try:
            # 4. 下載指定區間的股票資料
            df = yf.download(ticker_id, start=start_date, end=end_date_plus_one, progress=False, multi_level_index=False, auto_adjust=True)
            
            if not df.empty:
                df = df.reset_index()
                
                # 附加識別欄位：股票代號與對應的觸發日期
                df['stock_id'] = sid
                df['trigger_date'] = trigger_date_str
                df['name'] = item['名稱'] 
                
                # 5. 欄位名稱標準化
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                if 'volume' in df.columns:
                    df.rename(columns={'volume': 'Trading_Volume'}, inplace=True)
                if 'high' in df.columns:
                    df.rename(columns={'high': 'max'}, inplace=True)
                if 'low' in df.columns:
                    df.rename(columns={'low': 'min'}, inplace=True)
                    
                all_data.append(df)
            
            # 避免請求過於頻繁
            time.sleep(1)
            
        except Exception as e:
            print(f"⚠️ 抓取 {ticker_id} (觸發日期: {trigger_date_str}) 失敗: {e}")
            continue
            
    if not all_data:
        print("❌ 未抓取到任何資料")
        return pd.DataFrame()
        
    # 合併所有資料並重置 index
    final_df = pd.concat(all_data, ignore_index=True)
    return final_df


def get_fm_trading_days(start_str, end_str):
    """透過 FinMind API 批次取得指定區間內的台股交易日清單，回傳 Set 集合"""
    url = "https://api.finmindtrade.com/api/v4/data"
    parameters = {
        "dataset": "TaiwanStockTradingDate",
        "start_date": start_str,
        "end_date": end_str,
    }
    
    token = os.getenv("FINMIND_TOKEN")
    if token:
        parameters["token"] = token
        
    try:
        response = requests.get(url, params=parameters)
        result = response.json()
        if result.get("status") == 200 and result.get("data"):
            df_dates = pd.DataFrame(result["data"])
            if 'date' in df_dates.columns:
                return set(pd.to_datetime(df_dates['date']).dt.strftime("%Y-%m-%d"))
    except Exception as e:
        print(f"⚠️ 取得 FinMind 交易日清單失敗: {e}")
        
    return set()


def yf_fetch_all_stocks(stock_ids, start_date, end_date):
    """
    將原有的 FinMind 邏輯改為使用 yfinance 取得台股資料
    
    :param stock_ids: list, 例如 ['2330.TW', '2454.TW'] 或 ['2330', '2454']
    :param start_date: str, 格式 'YYYY-MM-DD'
    :param end_date: str, 格式 'YYYY-MM-DD'
    """
    all_data = []
    
    print(f"📡 正在透過 yfinance 抓取 {len(stock_ids)} 檔股票...")
  
    for sid in stock_ids:
        # 自動補齊台股後綴 (若使用者只輸入 2330)
        #ticker_id = f"{sid}.TW" if "." not in str(sid) else sid

        # 🌟 修正：如果是以 '^' 開頭的指數（如 '^TWII'），或是已經帶有 '.' 的代號，就不加 '.TW'
        if str(sid).startswith("^") or "." in str(sid):
            ticker_id = str(sid)
        else:
            ticker_id = f"{sid}.TW"
               
        try:
            # yfinance 下載資料
            # auto_adjust=True 會自動處理除權息調整價

            #因為yfinance抓資料時, 只會抓到end_date的前一天, 故傳入的end_date必須加1天, 再傳入download
            end_date_plus_one = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") 
            
            df = yf.download(ticker_id, start=start_date, end=end_date_plus_one, progress=False, multi_level_index=False, auto_adjust=True)
     
            if not df.empty:
                
                df.index = df.index.strftime('%Y-%m-%d') # 先把 Index 轉成字串
                                
                if end_date in df.index:
                    print(f"---{ticker_id} 在 {end_date} 的完整資料 ---")
                    #print(df.loc[end_date])  # 此時 loc[end_date] 還是有效的！
                else:
                    print(f"找不到 {end_date}")
                
                # 重整格式：yfinance 預設 index 是 Date，轉換成欄位方便合併
                df = df.reset_index()          
                
                # 加入股票代碼欄位以便後續辨識
                df['stock_id'] = sid
                
                # 統一欄位名稱為小寫 (符合原本 FinMind 習慣，自由選用)
                df.columns = [col.lower().replace(' ', '_') for col in df.columns]
                df.rename(columns={'volume': 'Trading_Volume'}, inplace=True)
                df.rename(columns={'high': 'max'}, inplace=True)
                df.rename(columns={'low': 'min'}, inplace=True)
        
                all_data.append(df)
            
            # 延遲避免請求過於頻繁
            time.sleep(2)

            #print(f"-----------{df}----------------")
            
        except Exception as e:
            print(f"⚠️ 抓取 {ticker_id} 失敗: {e}")
            continue
            
    if not all_data:
        print("❌ 未抓取到任何資料")
        return pd.DataFrame()
        
    # 合併所有資料並重置 index
    final_df = pd.concat(all_data, ignore_index=True)
    return final_df

def fm_fetch_all_stocks(dl, stock_ids, start_date, end_date):
    all_data = []
    
    print(f"串聯抓取 {len(stock_ids)} 檔股票...")
    
    for sid in stock_ids:
        try:
            # 逐一抓取
            df = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
            
            if df is not None and not df.empty:
                all_data.append(df)
            
            # 重要：如果您沒有 Token，建議加上微小延遲避免被封鎖
            time.sleep(0.5) 
            
        except Exception as e:
            print(f"⚠️ 抓取 {sid} 失敗: {e}")
            continue
            
    if not all_data:
        return pd.DataFrame()
        
    # 一次性垂直合併所有 Dataframe
    return pd.concat(all_data, ignore_index=True)
