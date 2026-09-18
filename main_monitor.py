import argparse
import os
import time
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils import (
    smart_read_csv,
    send_line_message,
    send_line_broadcast,
    get_stock_name_dict
)
from monitor.qiantang_monitor import mon_qiantang_sell_monitor

def fetch_finmind_all_data(dl, stock_ids: list, start_date: str, end_date: str) -> pd.DataFrame:
    """
    透過 FinMind API 統一抓取：
    1. K線資料 (TaiwanStockDaily)
    2. 三大法人買賣超 (TaiwanStockInstitutionalInvestorsBuySell)
    3. 融資融券餘額 (TaiwanStockMarginPurchaseShortSale)
    """
    if not dl:
        print("❌ 無法建立 FinMind DataLoader 物件")
        return pd.DataFrame()

    print(f"📡 正在透過 FinMind 批次抓取 {len(stock_ids)} 檔股票之 K 線與籌碼資料...")
    
    # 1. 一次性批次抓取 K 線資料
    try:
        df_daily = dl.taiwan_stock_daily(stock_id=stock_ids, start_date=start_date, end_date=end_date)
    except Exception as e:
        print(f"❌ FinMind 抓取 K 線資料失敗: {e}")
        return pd.DataFrame()

    if df_daily is None or df_daily.empty:
        print("⚠️ 未抓取到任何 K 線資料")
        return pd.DataFrame()

    # 欄位標準化對齊
    df_daily.rename(columns={
        'Trading_Volume': 'volume',
        'max': 'high',
        'min': 'low'
    }, inplace=True)
    
    # yfinance 習慣使用 max / min，在此同時保留兩者以避免策略讀取失敗
    df_daily['max'] = df_daily['high']
    df_daily['min'] = df_daily['low']

    # 2. 逐檔補充籌碼與信用交易資料
    chip_records = []
    for sid in stock_ids:
        try:
            # 2.1 三大法人資料
            df_inst = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date=start_date, end_date=end_date)
            # 2.2 融資融券資料
            df_margin = dl.taiwan_stock_margin_purchase_short_sale(stock_id=sid, start_date=start_date, end_date=end_date)

            df_chip = pd.DataFrame()

            # 彙整外資與主力買賣超
            if df_inst is not None and not df_inst.empty:
                df_foreign = df_inst[df_inst['name'].str.contains('Foreign', case=False, na=False)]
                df_foreign_net = df_foreign.groupby('date')['buy'].sum() - df_foreign.groupby('date')['sell'].sum()
                
                # 主力買賣超（三大法人合計買賣超）
                df_major_net = df_inst.groupby('date')['buy'].sum() - df_inst.groupby('date')['sell'].sum()

                df_chip = pd.DataFrame({
                    'foreign_net': df_foreign_net,
                    'major_net': df_major_net
                }).reset_index()

            # 彙整融資融券餘額
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

            time.sleep(0.3) # API 延遲保護

        except Exception as e:
            print(f"⚠️ 抓取 {sid} 籌碼資料失敗: {e}")
            continue

    # 3. 合併 K 線與籌碼 Dataframe
    if chip_records:
        df_all_chips = pd.concat(chip_records, ignore_index=True)
        final_df = pd.merge(df_daily, df_all_chips, on=['stock_id', 'date'], how='left')
    else:
        final_df = df_daily

    return final_df


def monitor_portfolio(user_id: str = None):
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    date_str = tw_time.strftime('%Y-%m-%d')
    
    # 1. 決定持股設定檔與 LINE 派發模式
    if user_id:
        csv_file = f"watch_list_{user_id}.csv"
        is_broadcast = False
        mode_desc = f"個人專屬模式 [{user_id}]"
    else:
        csv_file = "watch_list.csv"
        is_broadcast = True
        mode_desc = "預設全體廣播模式"

    if not os.path.exists(csv_file):
        print(f"❌ 找不到持股設定檔：{csv_file}")
        return

    # 2. 安全讀取 CSV
    portfolio_df = smart_read_csv(csv_file)
    if portfolio_df is None or portfolio_df.empty:
        print(f"❌ 讀取 {csv_file} 失敗或內容為空！")
        return

    print(f"📋 [啟動 {mode_desc}] 開始監控 {csv_file} 內共 {len(portfolio_df)} 檔持股...")

    stock_ids = portfolio_df['symbol'].astype(str).tolist()
    
    # 3. 取得 FinMind DataLoader 與基本資訊
    stock_name_dict, dl = get_stock_name_dict()

    # 4. 下載 FinMind K 線與籌碼整合資料
    start_date = (tw_time - timedelta(days=200)).strftime("%Y-%m-%d")
    end_date = date_str
    
    all_df = fetch_finmind_all_data(dl, stock_ids, start_date, end_date)
    if all_df.empty:
        print("⚠️ 無法取得股票歷史資料")
        return

    # 補齊籌碼預設欄位與缺失值 (fillna 0)
    for col in ['margin_balance', 'short_balance', 'foreign_net', 'major_net', 'broker_diff']:
        if col not in all_df.columns:
            all_df[col] = 0
        else:
            all_df[col] = all_df[col].fillna(0)

    # 5. 逐檔計算技術指標並執行錢塘潮 11 大防禦策略
    warnings = []
    grouped = all_df.groupby('stock_id')

    for idx, row in portfolio_df.iterrows():
        sid = str(row['symbol'])
        sname = row.get('name', stock_name_dict.get(sid, "未知"))
        cost_price = float(row.get('cost_price', 0))

        if sid not in grouped.groups:
            continue

        df_single = grouped.get_group(sid).sort_values('date').copy()

        # 輕鬆線與指標試算
        df_single['easy_line'] = df_single['close'].rolling(20).mean()
        df_single['easy_b'] = df_single['close'].ewm(span=5).mean()
        df_single['easy_s'] = df_single['close'].ewm(span=20).mean()

        # 9日 KD 隨機指標計算
        low_min = df_single['min'].rolling(9).min()
        high_max = df_single['max'].rolling(9).max()
        rsv = (df_single['close'] - low_min) / (high_max - low_min) * 100
        df_single['K'] = rsv.ewm(com=2).mean()
        df_single['D'] = df_single['K'].ewm(com=2).mean()

        # 執行 mon_qiantang_sell_monitor 進行健康檢查
        is_hit, info = mon_qiantang_sell_monitor(df_single, cost_price=cost_price)

        if is_hit:
            info['股票名稱'] = sname
            warnings.append(info)

    # 6. 發送 LINE 警報與回報
    if warnings:
        msg = f"🌊【錢塘潮持股健康檢查警報】{date_str}\n"
        msg += f"偵測到 {len(warnings)} 檔持股出現轉空/出貨訊號：\n\n"
        
        for w in warnings:
            msg += f"📌 {w['代號']} {w['股票名稱']}\n"
            msg += f"  • 當前價: ${w['收盤']} (成本: ${w['成本價']} | 報酬: {w['當前報酬']})\n"
            msg += f"  • 觸發賣訊: {w['轉空賣訊']}\n"
            msg += f"  • 操作建議: {w['操作建議']}\n"
            msg += "----------------------------------\n"

        print(f"\n📢 預覽發送內容：\n{msg}")

        if is_broadcast:
            send_line_broadcast(msg)
        else:
            send_line_message(user_id, msg)
    else:
        no_hit_msg = f"📅【錢塘潮持股健康檢查】{date_str}\n今日持股未觸發一柱清香、天女散花或打鐘下課等 11 大轉空賣訊。"
        print(f"✅ {no_hit_msg}")
        if is_broadcast:
            send_line_broadcast(no_hit_msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user_id", help="傳入 LINE User ID (若未傳入則預設讀取 watch_list.csv 並採用群發廣播)", nargs='?', default=None)
    args = parser.parse_args()

    monitor_portfolio(args.user_id)
