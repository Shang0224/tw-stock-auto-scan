from FinMind.data import DataLoader
import pandas as pd
from datetime import datetime, timedelta
import time

def st_near_ma240_df(df_single):
    """
    年線預備股策略：純計算邏輯，不負責抓取資料
    :param df_single: 該檔股票的歷史 Dataframe (由外部切片傳入)
    """

    print(f"st_near_ma240_df(  {len(df_single)})")
    
    # 1. 初始化
    is_in_range = False
    breakout_hits = {}

    # 2. 檢查資料長度 (需足夠計算 MA240)
    if df_single is None or len(df_single) < 240:
        print(f"df_single is None or len(df_single) < 240 {len(df_single) < 240}")
        return False, {}

    try:
        # 計算指標 (這裡建議只計算最後一筆，或對傳入的 df 進行計算)
        # 注意：df_single 已經包含了 500 天的資料
        ma240_series = df_single['close'].rolling(window=240).mean()
        
        today_price = df_single['close'].iloc[-1]
        today_ma240 = ma240_series.iloc[-1]
        
        if today_ma240 == 0 or pd.isna(today_ma240):
            print("today_ma240 == 0 or pd.isna(today_ma240):")
            return False, {}

        # 3. 邏輯判斷
        dist_ratio = (today_price - today_ma240) / today_ma240
        is_in_range = abs(dist_ratio) <= 0.03

        print(f"dist_ratio: {dist_ratio} today_price: {today_price} today_ma240: {today_ma240}  \n")
        
        if is_in_range:
            status = "年線上方強勢整理" if dist_ratio > 0 else "年線下方準備突破"
            
            breakout_hits = {
                "收盤": today_price,
                "年線位置": round(today_ma240, 2),
                "距離年線": f"{round(dist_ratio * 100, 2)}%",
                "狀態": status,
                "成交量": df_single['Trading_Volume'].iloc[-1] if 'Trading_Volume' in df_single.columns else 0
            }
            
    except Exception as e:
        print(f"❌ 處理 {sid} 邏輯時出錯: {e}")

    return is_in_range, breakout_hits

def st_near_ma240(sid, dl):
    """
    年線預備股策略：自主決定抓取 500 天資料
    """
    # 1. 先宣告預設值，確保不論結果如何，變數都存在
    is_in_range = False
    breakout_hits = {}
   
    # 策略決定需要的時間長度
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.datetime.now() - datetime.timedelta(days=500)).strftime("%Y-%m-%d")
    
    # 策略自主抓取資料
    df = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
    
    if df.empty or len(df) < 240:
        return False, breakout_hits

    # 計算邏輯
    #df['MA240'] = df['close'].rolling(240).mean()
    #today = df.iloc[-1]
    #dist_ratio = (today['close'] - today['MA240']) / today['MA240']
    
    #is_hit = abs(dist_ratio) <= 0.03

    try:
        # 抓取台股日成交資料 (建議 start_date 抓 500 天前以利計算與比較)
        df = dl.taiwan_stock_daily(
                        stock_id=sid,
                        start_date=start_date,
                        end_date=end_date)
            
        if len(df) < 240:
            return False, {}

        # 計算各指標
        df['MA20'] = df['close'].rolling(window=20).mean()   # 月線
        df['MA60'] = df['close'].rolling(window=60).mean()   # 季線
        df['MA240'] = df['close'].rolling(window=240).mean() # 年線
            
        today = df.iloc[-1]
            
        curr_price = today['close']
        ma240 = today['MA240']
        ma20 = today['MA20']
            
        # --- 邏輯抽換：預備股篩選清單 ---
            
        # 1. 價格區間：設定在年線上下 3% 範圍內
        # 公式：|股價 - 年線| / 年線 <= 0.03
        dist_ratio = (curr_price - ma240) / ma240
        is_in_range = abs(dist_ratio) <= 0.03
            
        # 2. 進階過濾：短線必須先轉強 (股價已站上月線)
        # 這能過濾掉「一路陰跌且尚未止跌」的股票
        #is_short_term_strong = curr_price > ma20

        #if is_in_range and is_short_term_strong:
        if is_in_range:
            # 判斷是在年線之上還是之下
            status = "年線上方強勢整理" if dist_ratio > 0 else "年線下方準備突破"
                
            breakout_hits = {
                    "股票代號": sid,
                    "今日收盤": curr_price,
                    "年線位置": round(ma240, 2),
                    "距離年線幅": f"{round(dist_ratio * 100, 2)}%",
                    "狀態": status,
                    "成交量": today['Trading_Volume']
                }
            print(f"🎯 發現預備標的：{sid} ({status})，距離比：{round(dist_ratio*100, 2)}%")
            
        # FinMind 頻率限制
        time.sleep(0.5)

    except Exception as e:
        print(f"❌ 處理 {sid} 時出錯: {e}")

    
    #return is_hit, {"年線": f"{round(today['MA240'], 2)}", "距離年線": f"{round(dist_ratio*100, 2)}%", "收盤": today['close']}

    print(f"strategy_near_ma240: {breakout_hits}  is_in_range : {is_in_range}")
    
    return is_in_range, breakout_hits



