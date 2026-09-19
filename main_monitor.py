import argparse
import os
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils import (
    smart_read_csv,
    send_line_message,
    send_line_broadcast,
    get_stock_name_dict,
    fm_get_complete_stock_data
)
# 🌟 匯入新架構的監控執行引擎
from monitor.engine import scan_sell_signals


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
    
    # 4. 抓取股票歷史與籌碼資料
    all_df = fm_get_complete_stock_data(dl, stock_ids, start_date, end_date)
    if all_df is None or all_df.empty:
        print("⚠️ 無法取得股票歷史與籌碼資料")
        return

    # 🌟 5. 執行持股賣訊防禦監控引擎
    # （指標計算如 KD、輕鬆線與多策略檢驗已在 monitor 引擎內部自動完成）
    warnings = scan_sell_signals(
        portfolio_df=portfolio_df,
        all_df=all_df
    )

    # 6. 派發 LINE 通知
    if warnings:
        msg = f"🌊【持股健康檢查警報】{date_str}\n"
        msg += f"偵測到 {len(warnings)} 檔持股出現轉空/出貨訊號：\n\n"
        
        for w in warnings:
            sname = w.get('stock_name', stock_name_dict.get(str(w['stock_id']), "未知"))
            cost_p = w.get('cost_price', 'N/A')
            close_p = w.get('close', 'N/A')
            ret_str = w.get('return_pct', 'N/A')
            
            msg += f"📌 {w['stock_id']} {sname}\n"
            msg += f"  • 當前價: ${close_p} (成本: ${cost_p} | 報酬: {ret_str})\n"
            msg += f"  • 觸發賣訊: {w['轉空賣訊']}\n"
            msg += f"  • 操作建議: {w['操作建議']}\n"
            msg += "----------------------------------\n"

        print(f"\n📢 預覽發送內容：\n{msg}")

        if is_broadcast:
            send_line_broadcast(msg)
        else:
            send_line_message(user_id, msg)
    else:
        no_hit_msg = f"📅【持股健康檢查】{date_str}\n今日持股狀態良好，未觸發任何防禦離場或轉空賣訊。"
        print(f"✅ {no_hit_msg}")
        if is_broadcast:
            send_line_broadcast(no_hit_msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user_id", help="傳入 LINE User ID (若未傳入則預設讀取 data/watch_list.csv 並採用群發廣播)", nargs='?', default=None)
    args = parser.parse_args()

    monitor_portfolio(args.user_id)
