# main_monitor.py
import argparse
import os
import pandas as pd
from datetime import datetime, timezone, timedelta

# 🌟 2. 匯入監控策略清單
from monitor.qiantang_monitor import (
    mon_qiantang_yi_zhu_qing_xiang,       # 一柱清香 (主力強勢鎖碼 / 籌碼高度集中)
    mon_qiantang_dang_tou_bang_he,        # 當頭棒喝 (主力逢高派發 / 籌碼高檔鬆動)
    mon_qiantang_ming_ri_huang_hua,       # 明日黃花 (籌碼退潮派發 / 主力撤退)
    mon_qiantang_tian_nv_san_hua,         # 天女散花 (籌碼高度分散 / 散戶狂接)
    mon_qiantang_xia_shan_meng_hu,         # 下山猛虎 (主力大幅派發 / 賣壓急湧)
    mon_qiantang_da_zhong_xia_ke,         # 打鐘下課 (散戶買超增加 / 籌碼趨於分散)
    mon_qiantang_he_shi,                  # 合十 (多頭籌碼強勢卡位)
    mon_qiantang_jiang_long_fu_hu,        # 降龍伏虎 (主力大舉洗盤 / 籌碼沉澱)

    #以下為底部轉折
    mon_qiantang_didi_chuanxin,           # 地底穿心
    mon_qiantang_ni_diu_ta_jian,          # 你丟他撿 (主力持續派發 / 散戶接盤)
    mon_qiantang_yuexia_laoren,           # 輕鬆轉空, 月下老人 (技術面/籌碼面轉空訊號)

    #這個不知道哪裡跑出來的
    mon_qiantang_kd_dead_cross,           # KD 死亡交叉, 可能是地底穿心 (高檔技術面反轉)
)

MONITORS = [
    #mon_qiantang_yi_zhu_qing_xiang,       # 一柱清香 (主力強勢鎖碼 / 籌碼高度集中)
    #mon_qiantang_dang_tou_bang_he,        # 當頭棒喝 (主力逢高派發 / 籌碼高檔鬆動)
    mon_qiantang_ming_ri_huang_hua,       # 明日黃花 (籌碼退潮派發 / 主力撤退)
    #mon_qiantang_tian_nv_san_hua,         # 天女散花 (籌碼高度分散 / 散戶狂接)
    #mon_qiantang_xia_shan_meng_hu,         # 下山猛虎 (主力大幅派發 / 賣壓急湧)
    #mon_qiantang_da_zhong_xia_ke,         # 打鐘下課 (散戶買超增加 / 籌碼趨於分散)
    #mon_qiantang_he_shi,                  # 合十 (多頭籌碼強勢卡位)
    #mon_qiantang_ni_diu_ta_jian,          # 你丟他撿 (主力持續派發 / 散戶接盤)
    #mon_qiantang_jiang_long_fu_hu,        # 降龍伏虎 (主力大舉洗盤 / 籌碼沉澱)
    #mon_qiantang_yuexia_laoren,           # 輕鬆轉空, 月下老人 (技術面/籌碼面轉空訊號)
    #mon_qiantang_kd_dead_cross,           # KD 死亡交叉, 可能是地底穿心 (高檔技術面反轉)
    #mon_qiantang_didi_chuanxin            # 地底穿心
]

from utils import (
    smart_read_csv,
    send_line_message,
    send_line_broadcast,
    get_stock_name_dict,
    fm_get_complete_stock_data
)

# 🌟 1. 額外匯入 preprocess_all_technical_indicators
from monitor.engine import (
    scan_sell_signals,
    preprocess_all_technical_indicators
)


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

    # 🌟 4.5 技術指標全域預處理 (全集中一次算出 KD、輕鬆線等)
    print("⚡ 正在計算全持股技術指標 (KD, 輕鬆線)...")
    all_df = preprocess_all_technical_indicators(all_df)

    # 🌟 5. 執行持股賣訊防禦監控引擎
    warnings = scan_sell_signals(
        portfolio_df=portfolio_df,
        all_df=all_df,
        monitor_list=MONITORS
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
            msg += f"  • 觸發賣訊: {w.get('轉空賣訊', w.get('strategy_name', '警報'))}\n"
            msg += f"  • 操作建議: {w.get('操作建議', '請注意籌碼風險')}\n"
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
    parser.add_argument("--user_id", help="傳入 LINE User ID", nargs='?', default=None)
    args = parser.parse_args()

    monitor_portfolio(args.user_id)
