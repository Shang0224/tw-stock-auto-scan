# utils/data_fetcher.py
import os
import requests
import yfinance as yf
import pandas as pd
import time
from FinMind.data import DataLoader
from datetime import datetime, timedelta, timezone

def get_stock_name_dict():
    """獲取全市場基本資訊名稱字典"""
    finmindtoken = os.getenv("FINMIND_ACCESS_TOKEN")    
    dl = DataLoader(token=finmindtoken)
    df_info = dl.taiwan_stock_info()
    return dict(zip(df_info['stock_id'], df_info['stock_name'])), dl

def fm_fetch_all_stocks(dl, stock_ids: list, start_date: str, end_date: str) -> pd.DataFrame:
    """抓取 FinMind 還原 K 線資料 (taiwan_stock_price_adj)"""
    all_data = []
    print(f"📡 串聯抓取 {len(stock_ids)} 檔股票之還原 K 線資料...")
    
    for sid in stock_ids:
        try:
            df = dl.taiwan_stock_price_adj(stock_id=sid, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                df = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)

            if df is not None and not df.empty:
                all_data.append(df)
            time.sleep(0.3)
        except Exception as e:
            print(f"⚠️ 抓取 {sid} 還原 K 線失敗: {e}")
            continue
            
    if not all_data:
        return pd.DataFrame()
        
    return pd.concat(all_data, ignore_index=True)

def fetch_finmind_chips_suspend(dl, stock_ids: list, start_date: str, end_date: str) -> pd.DataFrame:
    """抓取 FinMind 三大法人、融資融券與分點買賣家數差資料"""
    #沒有抓分點買賣資料的權限, 故只能停用
    chip_records = []
    print(f"📡 正在透過 FinMind 抓取籌碼、信用交易與分點資料...")

    for sid in stock_ids:
        try:
            # 1. 抓取三大法人與融資融券 (可傳入日期區間)
            df_inst = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date=start_date, end_date=end_date)
            df_margin = dl.taiwan_stock_margin_purchase_short_sale(stock_id=sid, start_date=start_date, end_date=end_date)

            df_chip = pd.DataFrame()

            if df_inst is not None and not df_inst.empty:
                df_foreign = df_inst[df_inst['name'].str.contains('Foreign', case=False, na=False)]
                
                #df_foreign_net = df_foreign.groupby('date')['buy'].sum() - df_foreign.groupby('date')['sell'].sum()
                #df_major_net = df_inst.groupby('date')['buy'].sum() - df_inst.groupby('date')['sell'].sum()
                # 轉為張數計算 (除以 1000)
                df_foreign_net = (df_foreign.groupby('date')['buy'].sum() - df_foreign.groupby('date')['sell'].sum()) / 1000
                df_major_net = (df_inst.groupby('date')['buy'].sum() - df_inst.groupby('date')['sell'].sum()) / 1000

                df_chip = pd.DataFrame({
                    'foreign_net': df_foreign_net,
                    'major_net': df_major_net
                }).reset_index()

            if df_margin is not None and not df_margin.empty:
                df_margin_sub = df_margin[['date', 'MarginPurchaseTodayBalance', 'ShortSaleTodayBalance']].copy()
                df_margin_sub.rename(columns={
                    'MarginPurchaseTodayBalance': 'margin_balance',
                    'ShortSaleTodayBalance': 'short_balance'
                }, inplace=True)

                if df_chip.empty:
                    df_chip = df_margin_sub
                else:
                    df_chip = pd.merge(df_chip, df_margin_sub, on='date', how='outer')

            # 2. 抓取最新一日分點明細計算買賣家數差 (使用單日參數 date=end_date)
            df_chip['broker_diff'] = 0  # 預設為 0
            try:
                # 🌟 正確傳入單日參數 date=end_date
                df_broker = dl.taiwan_stock_trading_daily_report(stock_id=sid, date=end_date)
                
                if df_broker is not None and not df_broker.empty:
                    # 判斷欄位名稱 (FinMind 分點欄位通常為 buy/sell 或 buy_volume/sell_volume)
                    buy_col = 'buy' if 'buy' in df_broker.columns else ('buy_volume' if 'buy_volume' in df_broker.columns else None)
                    sell_col = 'sell' if 'sell' in df_broker.columns else ('sell_volume' if 'sell_volume' in df_broker.columns else None)

                    if buy_col and sell_col:
                        buy_brokers = (df_broker[buy_col] > 0).sum()
                        sell_brokers = (df_broker[sell_col] > 0).sum()
                        broker_diff = buy_brokers - sell_brokers

                        # 將最新一天的 broker_diff 填入 df_chip 當天紀錄中
                        df_chip.loc[df_chip['date'] == end_date, 'broker_diff'] = broker_diff
                else:
                    print(f"⚠️ [Fallback] 股票 {sid} 於 {end_date} 無分點日報 (可能未開盤或資料未更新)，'broker_diff' 保持 0")

            except Exception as e_broker:
                print(f"⚠️ [Fallback 觸發] 股票 {sid} 抓取分點日報失敗 (原因: {e_broker})，'broker_diff' 自動降級填補 0")

            # 3. 彙整單檔籌碼紀錄
            if not df_chip.empty:
                df_chip['stock_id'] = sid
                chip_records.append(df_chip)

            time.sleep(0.3)

        except Exception as e:
            print(f"⚠️ 抓取 {sid} 籌碼失敗: {e}")
            continue

    if chip_records:
        return pd.concat(chip_records, ignore_index=True)
    return pd.DataFrame()


def fetch_finmind_chips(dl, stock_ids: list, start_date: str, end_date: str) -> pd.DataFrame:
    """抓取 FinMind 三大法人與融資融券籌碼資料"""
    chip_records = []
    print(f"📡 正在透過 FinMind 抓取籌碼與信用交易資料...")

    for sid in stock_ids:
        try:
            df_inst = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date=start_date, end_date=end_date)
            df_margin = dl.taiwan_stock_margin_purchase_short_sale(stock_id=sid, start_date=start_date, end_date=end_date)

            df_chip = pd.DataFrame()

            if df_inst is not None and not df_inst.empty:
                df_foreign = df_inst[df_inst['name'].str.contains('Foreign', case=False, na=False)]
                df_foreign_net = df_foreign.groupby('date')['buy'].sum() - df_foreign.groupby('date')['sell'].sum()
                df_major_net = df_inst.groupby('date')['buy'].sum() - df_inst.groupby('date')['sell'].sum()

                df_chip = pd.DataFrame({
                    'foreign_net': df_foreign_net,
                    'major_net': df_major_net
                }).reset_index()

            if df_margin is not None and not df_margin.empty:
                df_margin_sub = df_margin[['date', 'MarginPurchaseTodayBalance', 'ShortSaleTodayBalance']].copy()
                df_margin_sub.rename(columns={
                    'MarginPurchaseTodayBalance': 'margin_balance',
                    'ShortSaleTodayBalance': 'short_balance'
                }, inplace=True)

                if df_chip.empty:
                    df_chip = df_margin_sub
                else:
                    df_chip = pd.merge(df_chip, df_margin_sub, on='date', how='outer')

            if not df_chip.empty:
                df_chip['stock_id'] = sid
                chip_records.append(df_chip)

                # 🌟 印出當前股票的籌碼 DataFrame 內容
                #print(f"\n📊 --- 股票 {sid} 籌碼資料 ---")
                #print(df_chip.to_string(index=False))  # to_string(index=False) 可隱藏預設的索引欄位，讓排版更整齊
                #print("-" * 40)

            time.sleep(0.3)

        except Exception as e:
            print(f"⚠️ 抓取 {sid} 籌碼失敗: {e}")
            continue

    if chip_records:
        return pd.concat(chip_records, ignore_index=True)
    return pd.DataFrame()


def fm_get_complete_stock_data(dl, stock_ids: list, start_date: str, end_date: str) -> pd.DataFrame:
    """
    🌟 高階包裝函數：統一取得 FinMind 還原 K 線 + 籌碼資料並自動合併
    """
    # 1. 抓取 K 線
    df_daily = fm_fetch_all_stocks(dl, stock_ids, start_date, end_date)
    if df_daily.empty:
        return pd.DataFrame()

    # 2. 抓取籌碼
    df_chips = fetch_finmind_chips(dl, stock_ids, start_date, end_date)

    # 3. 合併資料
    if not df_chips.empty:
        all_df = pd.merge(df_daily, df_chips, on=['stock_id', 'date'], how='left')
    else:
        all_df = df_daily

    # 4. 補齊策略所需的預設欄位 (避免 KeyError)
    for col in ['margin_balance', 'short_balance', 'foreign_net', 'major_net', 'broker_diff']:
        if col not in all_df.columns:
            print(f"🆕 [欄位檢查] 缺少欄位 '{col}'，已自動新增並補 0")
            all_df[col] = 0
        else:
            all_df[col] = all_df[col].fillna(0)

    return all_df

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
