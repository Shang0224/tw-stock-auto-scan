import argparse
import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils import (
    yf_fetch_all_stocks,
    send_line_message,       # 單推指定用戶 (Push)
    send_line_broadcast,     # 廣播群發 (Broadcast)
    save_scan_report,
    archive_and_cleanup
)
from monitor.qiantang_monitor import mon_qiantang_sell_monitor

def monitor_portfolio(user_id: str = None):
    """
    持股健康檢查與轉空警報系統：
    - 若指定 user_id：讀取 watch_list_{user_id}.csv，以 Push Message 單推給該用戶。
    - 若未指定 user_id：讀取 watch_list.csv，以 Broadcast Message 廣播群發。
    """
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    date_str = tw_time.strftime('%Y-%m-%d')
    
    # 1. 動態判定 CSV 檔名與 LINE 發送模式
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

    # 2. 讀取持股清單與成本價
    portfolio_df = pd.read_csv(csv_file)
    print(f"📋 [啟動 {mode_desc}] 開始監控 {csv_file} 內共 {len(portfolio_df)} 檔持股...")

    stock_ids = portfolio_df['symbol'].astype(str).tolist()
    
    # 3. 抓取 K 線數據
    start_date = (tw_time - timedelta(days=200)).strftime("%Y-%m-%d")
    end_date = date_str
    all_df = yf_fetch_all_stocks(stock_ids, start_date, end_date)

    if all_df.empty:
        print("⚠️ 無法取得股票 K 線資料")
        return

    # 4. 逐檔檢查錢塘潮賣出/警告訊號
    warnings = []
    grouped = all_df.groupby('stock_id')

    for idx, row in portfolio_df.iterrows():
        sid = str(row['symbol'])
        sname = row['name']
        cost_price = float(row.get('cost_price', 0))

        if sid not in grouped.groups:
            continue

        df_single = grouped.get_group(sid).sort_values('date')
        
        # 執行錢塘潮轉空/出貨/換手監控
        is_hit, info = st_qiantang_sell_monitor(df_single, cost_price=cost_price)

        if is_hit:
            info['股票名稱'] = sname
            warnings.append(info)

    # 5. 組裝訊息與分流派發
    if warnings:
        msg = f"🌊【錢塘潮持股健康檢查警報】{date_str}\n"
        msg += f"偵測到 {len(warnings)} 檔持股出現轉空/出貨訊號：\n\n"
        
        for w in warnings:
            msg += f"📌 {w['代號']} {w['股票名稱']}\n"
            msg += f"  • 當前價: ${w['收盤']} (成本: ${w['成本價']} | 報酬: {w['當前報酬']})\n"
            msg += f"  • 觸發賣訊: {w['轉空賣訊']}\n"
            msg += f"  • 操作建議: {w['操作建議']}\n"
            msg += "----------------------------------\n"

        print(f"\n📢 預覽要發送的訊息內容：\n{msg}")

        # 依模式派發 LINE 訊息
        if is_broadcast:
            print("📡 正在執行 LINE 全體廣播發送 (Broadcast)...")
            send_line_broadcast(msg)
        else:
            print(f"🎯 正在執行 LINE 個人專屬推播 (Push to {user_id})...")
            # send_line_message 內部會將訊息推給指定 user_id
            send_line_message(user_id, msg)
    else:
        no_hit_msg = f"📅【錢塘潮持股健康檢查】{date_str}\n今日監控持股狀況良好，未觸發一柱清香、天女散花或打鐘下課等賣訊。"
        print(f"✅ {no_hit_msg}")
        
        # 如果是廣播模式且無訊號，也可以選擇廣播回報平安
        if is_broadcast:
            send_line_broadcast(no_hit_msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # 將 user_id 設為選填 (nargs='?')
    parser.add_argument("--user_id", help="傳入 LINE User ID (若未傳入則預設讀取 watch_list.csv 並採用群發廣播)", nargs='?', default=None)
    args = parser.parse_args()

    monitor_portfolio(args.user_id)
    
