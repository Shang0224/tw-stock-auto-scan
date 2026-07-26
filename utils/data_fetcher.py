# utils/data_fetcher.py
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta, timezone
import time


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
        ticker_id = f"{sid}.TW" if "." not in str(sid) else sid
               
        try:
            # yfinance 下載資料
            # auto_adjust=True 會自動處理除權息調整價

            #因為yfinance抓資料時, 只會抓到end_date的前一天, 故傳入的end_date必須加1天, 再傳入download
            end_date_plus_one = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") 
            
            df = yf.download(ticker_id, start=start_date, end=end_date_plus_one, progress=False, multi_level_index=False)
     
            if not df.empty:
                
                df.index = df.index.strftime('%Y-%m-%d') # 先把 Index 轉成字串
                                
                if end_date in df.index:
                    print(f"---{ticker_id} 在 {end_date} 的完整資料 ---")
                    print(df.loc[end_date])  # 此時 loc[end_date] 還是有效的！
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

                df.rename(columns={'close': 'real close'}, inplace=True)
                df.rename(columns={'adj close': 'close'}, inplace=True)
        
                all_data.append(df)
            
            # 延遲避免請求過於頻繁
            time.sleep(2)
            
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
