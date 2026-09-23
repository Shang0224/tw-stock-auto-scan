import os
import pandas as pd
from datetime import datetime, timedelta, timezone

# 🌟 1. 匯入 engine 的全域預處理與單股檢測核心，以及 PARAM_PROFILES
from monitor.engine import (
    preprocess_all_technical_indicators,
    scan_single_stock_monitors,
    PARAM_PROFILES
)

# 🌟 2. 匯入監控策略清單 (也可視需求自 monitor.registry 匯入 ACTIVE_MONITORS)
from monitor.qiantang_monitor import (
    mon_qiantang_yi_zhu_qing_xiang,       # 一柱清香 (主力強勢鎖碼 / 籌碼高度集中)
    mon_qiantang_dang_tou_bang_he,        # 當頭棒喝 (主力逢高派發 / 籌碼高檔鬆動)
    mon_qiantang_ming_ri_huang_hua,       # 明日黃花 (籌碼退潮派發 / 主力撤退)
    mon_qiantang_tian_nv_san_hua,         # 天女散花 (籌碼高度分散 / 散戶狂接)
    mon_qiantang_xia_shan_meng_hu,         # 下山猛虎 (主力大幅派發 / 賣壓急湧)
    mon_qiantang_da_zhong_xia_ke,         # 打鐘下課 (散戶買超增加 / 籌碼趨於分散)
    mon_qiantang_he_shi,                  # 合十 (多頭籌碼強勢卡位)
    mon_qiantang_ni_diu_wo_jian,          # 你丟我撿 (主力持續派發 / 散戶接盤)
    mon_qiantang_jiang_long_fu_hu,        # 降龍伏虎 (主力大舉洗盤 / 籌碼沉澱)
    mon_qiantang_qing_song_xian_zhuan_kong,# 輕鬆轉空, 月下老人 (技術面/籌碼面轉空訊號)
    mon_qiantang_kd_dead_cross,           # KD 死亡交叉, 可能是地底穿心 (高檔技術面反轉)
)

# 🌟 3. 匯入 utils 工具庫
from utils import (
    get_stock_name_dict,
    parse_monitor_stocks,
    fm_get_complete_stock_data,
    save_multi_day_report,
    archive_and_cleanup,
    send_email_report,
    align_and_normalize_results,
    calculate_forward_horizon_returns,
    get_fm_trading_days
)

# =====================================================================
# 🎛️ 測試環境控制面板
# =====================================================================
CHOSEN_SOURCE = 'fm' 

TEST_START_DATE = '2024-01-01'
TEST_END_DATE   = '2025-09-30'

# ---------------------------------------------------------------------
# 模式 A：CSV 檔案載入模式
# STOCK_MODE = 'csv'
# STOCK_INPUT = 'watch_list.csv'

# 模式 B：自訂 List[dict] 載入模式
STOCK_MODE = 'noncsv'
STOCK_INPUT = [
    #{'stock_id': '2330', 'name': '台積電', 'category': 'TW50'},
    {'stock_id': '3706', 'name': '神達', 'category': 'MID100'},
    #{'stock_id': '2317', 'name': '鴻海', 'category': 'TW50'},
    #{'stock_id': '3227', 'name': '原相', 'category': 'ICDesign'}
]
# ---------------------------------------------------------------------

TEST_MONITOR = [
    #mon_qiantang_yi_zhu_qing_xiang,       # 一柱清香 (主力強勢鎖碼 / 籌碼高度集中)
    mon_qiantang_dang_tou_bang_he,        # 當頭棒喝 (主力逢高派發 / 籌碼高檔鬆動)
    #mon_qiantang_ming_ri_huang_hua,       # 明日黃花 (籌碼退潮派發 / 主力撤退)
    #mon_qiantang_tian_nv_san_hua,         # 天女散花 (籌碼高度分散 / 散戶狂接)
    #mon_qiantang_xia_shan_meng_hu,         # 下山猛虎 (主力大幅派發 / 賣壓急湧)
    #mon_qiantang_da_zhong_xia_ke,         # 打鐘下課 (散戶買超增加 / 籌碼趨於分散)
    #mon_qiantang_he_shi,                  # 合十 (多頭籌碼強勢卡位)
    #mon_qiantang_ni_diu_wo_jian,          # 你丟我撿 (主力持續派發 / 散戶接盤)
    #mon_qiantang_jiang_long_fu_hu,        # 降龍伏虎 (主力大舉洗盤 / 籌碼沉澱)
    #mon_qiantang_qing_song_xian_zhuan_kong,# 輕鬆轉空, 月下老人 (技術面/籌碼面轉空訊號)
    #mon_qiantang_kd_dead_cross,           # KD 死亡交叉, 可能是地底穿心 (高檔技術面反轉)
]

DAYS_BEFORE = 365  # 歷史計算指標用的緩衝天數


def scan_monitor_day(day_str, all_df_slice, monitor_stocks, strategies, profiles_map=PARAM_PROFILES):
    """
    單日個股監控掃描核心：
    在當日歷史切片 (all_df_slice) 下，透過 scan_single_stock_monitors 檢測策略
    """
    day_hits = []
    
    # 建立 stock_id 到 monitor Meta 的快速查詢表
    stock_meta_map = {str(s['stock_id']): s for s in monitor_stocks}
    
    grouped = all_df_slice.groupby('stock_id')
    
    for stock_id, group_df in grouped:
        sid = str(stock_id)
        if sid not in stock_meta_map:
            continue
            
        meta = stock_meta_map[sid]
        stock_name = meta.get('name', group_df['name'].iloc[-1] if 'name' in group_df.columns else sid)
        stock_cat = meta.get('category', group_df['category'].iloc[-1] if 'category' in group_df.columns else 'default')
        
        # 排序 K 線
        df_single = group_df.sort_values('date').copy()
        
        # 🌟 呼叫 engine.py 的核心元件 (直接重用前置預處理好的指標，極速運算)
        hits = scan_single_stock_monitors(
            df_single=df_single,
            category=stock_cat,
            monitor_list=strategies,
            param_profiles=profiles_map
        )
        
        for hit in hits:
            hit_record = {
                "date": day_str,
                "stock_id": sid,
                "name": str(stock_name),
            }
            hit_record.update(hit)
            day_hits.append(hit_record)
                
    return day_hits


def run_monitor_test(source, stock_source, stock_input, strategies, start_date_str, end_date_str):
    """採用 test_scan 橫向時間軸架構與全域預處理的個股監控測試引擎"""
    tz_tw = timezone(timedelta(hours=8))
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=tz_tw)

    if end_date < start_date:
        raise ValueError("❌ 結束日期不能小於開始日期！")

    # 1. 解析監控股票清單
    monitor_stocks = parse_monitor_stocks(stock_source, stock_input)
    if not monitor_stocks:
        print("❌ [錯誤] 無有效的監控股票資料。")
        return

    source_label = os.path.basename(stock_input) if stock_source == 'csv' else "自訂個股清單 (List)"
    unique_stock_ids = list(set([str(s['stock_id']) for s in monitor_stocks]))

    print(f"🧪 [測試啟動] 模式：固定區間個股監控 ({start_date_str} ~ {end_date_str})")
    print(f"📡 資料來源：{source.upper()} | 監控數量：{len(unique_stock_ids)} 檔個股 ({source_label})")

    # 2. 準備歷史資料抓取區間
    fetch_start_str = (start_date - timedelta(days=DAYS_BEFORE)).strftime("%Y-%m-%d")
    fetch_end_str = (end_date + timedelta(days=60)).strftime("%Y-%m-%d")  # 預留未來天數計算前瞻績效

    print(f"📡 正在抓取全段歷史與籌碼資料 ({fetch_start_str} ~ {fetch_end_str})...")

    stock_name_dict, dl = get_stock_name_dict()

    if source.lower() == 'fm':
        global_df = fm_get_complete_stock_data(dl, unique_stock_ids, fetch_start_str, fetch_end_str)
        df_meta = pd.DataFrame(monitor_stocks)
        if not global_df.empty and 'category' in df_meta.columns:
            global_df = pd.merge(global_df, df_meta[['stock_id', 'category']], on='stock_id', how='left')
            print("🏷️ [類別載入成功] category 欄位已完美對齊至交易資料中！")
    else:
        raise ValueError("❌ 測試錢塘潮策略請務必將 CHOSEN_SOURCE 設定為 'fm'")

    if global_df.empty:
        print(f"❌ [{source.upper()} 測試失敗] 抓取歷史資料為空！")
        return

    # 🌟 3. 【全域預處理】一次性預先算好所有股票的 KD 與輕鬆線指標
    print("⚡ 正在計算全歷史技術指標 (KD, 輕鬆線)...")
    global_df = preprocess_all_technical_indicators(global_df)
    print("✅ 全域指標預處理完成！")

    # 4. 預先取得台股交易日清單 (跳過非交易日)
    print("📡 正在向 FinMind 取得台股交易日曆行事曆...")
    trading_days_set = get_fm_trading_days(fetch_start_str, fetch_end_str)
    if trading_days_set:
        print(f"✅ 成功載入 FinMind 交易日清單，共 {len(trading_days_set)} 個交易日。")
    else:
        print("⚠️ 無法取得 FinMind 交易日，將自動退回僅過濾週末的預設機制。")

    # 5. 逐日推進監控掃描 (Date-centric Loop)
    collected_range_results = {}
    current_day = start_date

    while current_day <= end_date:
        day_str = current_day.strftime("%Y-%m-%d")

        # 交易日過濾
        if trading_days_set:
            if day_str not in trading_days_set:
                current_day += timedelta(days=1)
                continue
        else:
            if current_day.weekday() >= 5:
                current_day += timedelta(days=1)
                continue

        # 切出截至當日為止的歷史切片
        day_data_cutoff = current_day.replace(hour=23, minute=59, second=59)
        all_df_slice = global_df[global_df['date'] <= day_data_cutoff.strftime("%Y-%m-%d")].copy()

        if all_df_slice.empty:
            current_day += timedelta(days=1)
            continue

        # 執行當日監控掃描
        day_hits = scan_monitor_day(
            day_str=day_str,
            all_df_slice=all_df_slice,
            monitor_stocks=monitor_stocks,
            strategies=strategies,
            profiles_map=PARAM_PROFILES
        )

        if day_hits:
            print(f"⚡ [{day_str}] 監控掃描完成，共觸發 {len(day_hits)} 筆訊號。")
            
            # 6. 【流程解耦】統一計算前瞻績效 (Horizon Returns: 3, 5, 10, 20日)
            for hit in day_hits:
                horizon_perf = calculate_forward_horizon_returns(
                    hit["stock_id"], day_str, global_df, horizons=[3, 5, 10, 20]
                )
                hit.update(horizon_perf)

            collected_range_results[day_str] = day_hits

        current_day += timedelta(days=1)

    # 7. 彙整數據、格式化、寫入首行註記與產出報表
    if collected_range_results:
        priority_keys = ["date", "stock_id", "name", "category", "strategy_name"]
        collected_range_results = align_and_normalize_results(collected_range_results, priority_keys=priority_keys)

        strat_names = [strat.__name__ for strat in strategies]
        strat_header_line = f"#測試監控策略清單:, {', '.join(strat_names)} , | , 監控區間: {start_date_str} ~ {end_date_str}\n"

        strat_label = strat_names[0] if len(strat_names) == 1 else f"multi_monitor_{len(strat_names)}"
        output_name = f"monitor_{strat_label}"
        now_time = datetime.now(timezone(timedelta(hours=8)))

        # 產出標準 CSV 報表
        csv_path = save_multi_day_report(collected_range_results, output_name, now_time)
        print(f"✅ [報表產出成功] 已格式化輸出：{csv_path}")

        # 將策略與區間註記動態插隊寫入 CSV 第一行
        if csv_path and os.path.exists(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    original_content = f.read()

                with open(csv_path, 'w', encoding='utf-8-sig') as f:
                    f.write(strat_header_line)
                    f.write(original_content)

                print(f"✍️  [策略註記成功] 已寫入首行標頭：{strat_header_line.strip()}")
            except Exception as e:
                print(f"⚠️ [寫入策略註腳失敗] 錯誤: {e}")

        # 發送 Email 報告
        #send_email_report(csv_path)

        # 上傳 NAS 遠端封存
        if os.path.exists(csv_path):
            current_time_str = now_time.strftime("%Y%m%d_%H%M")
            remote_filename = f"{output_name}_range_{start_date_str}_to_{end_date_str}_{current_time_str}.csv"
            remote_test_path = f"{os.getenv('NAS_SFTP_PATH')}/qiantang_monitor_reports/{remote_filename}"

            try:
                print(f"📦 啟動遠端封存與清理流程...")
                archive_and_cleanup(local_file_path=csv_path, remote_path=remote_test_path)
                print(f"🚀 [NAS 同步成功] 檔案已送達遠端：qiantang_monitor_reports/{remote_filename}")
            except Exception as e:
                print(f"⚠️ [自動封存/上傳失敗] 錯誤: {e}")
    else:
        print(f"\nℹ️ 監控策略在 {start_date_str} ~ {end_date_str} 區間內皆無符合條件之標的。")

    print(f"\n🎉 監控測試任務已全部執行完畢！")


if __name__ == "__main__":
    print("=== 進入固定區間個股監控測試環境 ===")

    run_monitor_test(
        source=CHOSEN_SOURCE,
        stock_source=STOCK_MODE,
        stock_input=STOCK_INPUT,
        strategies=TEST_MONITOR,
        start_date_str=TEST_START_DATE,
        end_date_str=TEST_END_DATE
    )
