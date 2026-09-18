import argparse
import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils import (
    smart_read_csv,
    send_line_message,
    send_line_broadcast,
    get_stock_name_dict,
    fm_get_complete_stock_data  # 🌟 更新函式名稱
)
from monitor.qiantang_monitor import mon_qiantang_sell_monitor

def monitor_portfolio(user_id: str = None):
    tz_tw = timezone(timedelta(hours=8))
    tw_time = datetime.now(tz_tw)
    date_str = tw_time.strftime('%Y-%m-%d')
    
    # 1. 決定設定檔路徑
    if user_id:
        csv_file = os.path.join("data", f"watch_list_{user_id}.csv")
        is_broadcast = False
        mode_desc = f"個人專屬模式 [{user_id}]"
    else:
        csv_file = os.path.join("data", "watch_list.csv")
        is_broadcast = True
        mode_desc = "預設全體廣播模式"

    if not os.path.exists(csv_file):
        print(f"❌ 找不到持股設定檔：{csv_file}")
        return

    # 2. 讀取 CSV
    portfolio_df = smart_read_csv(csv_file)
    if portfolio_df is None or portfolio_df.empty:
        print(f"❌ 讀取 {csv_file} 失敗或內容為空！")
        return

    print(f"📋 [啟動 {mode_desc}] 開始監控 {csv_file} 內共 {len(portfolio_df)} 檔持股...")
    stock_ids = portfolio_df['stock_id'].astype(str).tolist()
    
    # 3. 取得 FinMind DataLoader
    stock_name_dict, dl = get_stock_name_dict()

    start_date = (tw_time - timedelta(days=200)).strftime("%Y-%m-%d")
    end_date = date_str
    
    # 🌟 4. 呼叫新的包含前綴函式
    all_df = fm_get_complete_stock_data(dl, stock_ids, start_date, end_date)
    if all_df.empty:
        print("⚠️ 無法取得股票歷史與籌碼資料")
        return

    # 5. 逐檔運算技術指標並執行錢塘潮 11 大防禦賣訊監控
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

        # 9日 KD 試算
        low_min = df_single['min'].rolling(9).min()
        high_max = df_single['max'].rolling(9).max()
        rsv = (df_single['close'] - low_min) / (high_max - low_min) * 100
        df_single['K'] = rsv.ewm(com=2).mean()
        df_single['D'] = df_single['K'].ewm(com=2).mean()

        # 執行 11 大防禦賣訊監控策略
        is_hit, info = mon_qiantang_sell_monitor(df_single, cost_price=cost_price)

        if is_hit:
            info['股票名稱'] = sname
            warnings.append(info)

    # 6. 派發 LINE 通知
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
    parser.add_argument("--user_id", help="傳入 LINE User ID (若未傳入則預設讀取 data/watch_list.csv 並採用群發廣播)", nargs='?', default=None)
    args = parser.parse_args()

    monitor_portfolio(args.user_id)
