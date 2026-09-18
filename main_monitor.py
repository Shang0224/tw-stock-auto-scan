import argparse
import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils import (
    yf_fetch_all_stocks,
    parse_stock_ids,
    send_line_message,
    save_scan_report,
    archive_and_cleanup
)
from strategy.st_qiantang_sell import st_qiantang_sell_monitor

def monitor_user_portfolio(user_id: str):
    """
    對特定 User ID 的持股進行錢塘潮轉空/出貨/換手監控
    """
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    date_str = tw_time.strftime('%Y-%m-%d')
    
    csv_file = f"watch_list_{user_id}.csv"
    if not os.path.exists(csv_file):
        print(f"❌ 找不到使用者持股設定檔: {csv_file}")
        return

    # 1. 讀取該好友的持股清單與成本價
    portfolio_df = pd.read_csv(csv_file)
    print(f"📋 開始為 User [{user_id}] 監控 {len(portfolio_df)} 檔持股...")

    stock_ids = portfolio_df['symbol'].astype(str).tolist()
    
    # 2. 抓取 K 線數據
    start_date = (tw_time - timedelta(days=200)).strftime("%Y-%m-%d")
    end_date = date_str
    all_df = yf_fetch_all_stocks(stock_ids, start_date, end_date)

    if all_df.empty:
        print("⚠️ 無法取得股票 K 線資料")
        return

    # 3. 逐檔檢查賣出/警告訊號
    warnings = []
    grouped = all_df.groupby('stock_id')

    for idx, row in portfolio_df.iterrows():
        sid = str(row['symbol'])
        sname = row['name']
        cost_price = float(row['cost_price'])

        if sid not in grouped.groups:
            continue

        df_single = grouped.get_group(sid).sort_values('date')
        
        # 執行錢塘潮轉空/出貨/換手監控
        is_hit, info = st_qiantang_sell_monitor(df_single, cost_price=cost_price)

        if is_hit:
            info['股票名稱'] = sname
            warnings.append(info)

    # 4. 發送 LINE 個人專屬卡片/警報
    if warnings:
        msg = f"🌊【錢塘潮持股健康檢查警報】{date_str}\n"
        msg += f"偵測到 {len(warnings)} 檔持股出現轉空/出貨訊號：\n\n"
        
        for w in warnings:
            msg += f"📌 {w['代號']} {w['股票名稱']}\n"
            msg += f"  • 當前價: ${w['收盤']} (成本: ${w['成本價']} | 報酬: {w['當前報酬']})\n"
            msg += f"  • 觸發賣訊: {w['轉空賣訊']}\n"
            msg += f"  • 操作建議: {w['操作建議']}\n"
            msg += "----------------------------------\n"

        print(msg)
        # 發送給指定 user_id
        # send_line_message(user_id, msg)
    else:
        print(f"✅ User [{user_id}] 今日持股狀況良好，未觸發一柱清香、天女散花或打鐘下課等賣訊。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user_id", help="傳入 LINE User ID", required=True)
    args = parser.parse_args()

    monitor_user_portfolio(args.user_id)
