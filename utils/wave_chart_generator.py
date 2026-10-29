# utils/wave_chart_generator.py
import os
import re
import shutil
from datetime import datetime
import matplotlib
import matplotlib.dates as mdates
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_perf_field(val):
    """解析 1Y內最高績效 / 持倉最高績效 / 1Y內最低績效 / 持倉實際最低績效 欄位字串。

    支援格式範例:
      - '+40.99% (2026-06-03)'
      - '40.99% (2026-06-03)'
      - '-24.38% $$2026-03-04$$'
      - '-22.93% (2026-05-18)'
    傳回: (pct_float, date_str) 或 (None, None)
    """
    if pd.isna(val) or not isinstance(val, str):
        return None, None
    m = re.search(r'([+\-\d.]+)%\s*[\(\$]+([\d]{4}-\d{2}-\d{2})', val)
    if m:
        return float(m.group(1)), m.group(2)
    return None, None


def group_signals_into_waves(stock_df):
    """依據『波段群組編號』對單一股票的所有觸發訊號進行精準波段歸類，並擷取首發標籤與極值。"""
    s_df = stock_df.sort_values('日期').copy()

    # 🛡️ 容錯防護：若傳入資料未包含『波段群組編號』，自動動態補算去重編號
    if '波段群組編號' not in s_df.columns:
        from utils.analytics import calculate_wave_dedup_info
        records = calculate_wave_dedup_info(s_df.to_dict('records'))
        s_df = pd.DataFrame(records).sort_values('日期')

    waves = []

    for wave_id, w_df in s_df.groupby('波段群組編號', sort=False):
        w_df = w_df.sort_values('日期')
        first_row = w_df.iloc

        # 🌟 擷取首發訊號之『走勢類別標籤』，預設值無資料時顯示為 "NA"
        raw_cat = first_row.get('走勢類別標籤', 'NA')
        cat_tag = str(raw_cat).strip() if (pd.notna(raw_cat) and str(raw_cat).strip()) else 'NA'

        # 解析 1Y 極值
        high_pct, c_high_date = parse_perf_field(first_row.get('1Y內最高績效', ''))
        low_pct, c_low_date = parse_perf_field(first_row.get('1Y內最低績效', ''))

        # 解析 持倉 極值 (若無則自動降級退回 1Y 極值)
        h_hold_pct, h_hold_date = parse_perf_field(first_row.get('持倉最高績效', ''))
        l_hold_pct, l_hold_date = parse_perf_field(first_row.get('持倉實際最低績效', ''))

        if h_hold_date is None:
            h_hold_pct, h_hold_date = high_pct, c_high_date
        if l_hold_date is None:
            l_hold_pct, l_hold_date = low_pct, c_low_date

        first_trigger_dt = pd.to_datetime(w_df['日期'].min())
        last_trigger_dt = pd.to_datetime(w_df['日期'].max())

        start_date = first_trigger_dt - pd.DateOffset(months=1)
        end_date = last_trigger_dt + pd.DateOffset(months=13)

        waves.append({
            'stock_id': str(first_row['股票代號']),
            'stock_name': str(first_row['名稱']),
            'group_id': str(wave_id),
            'cat_tag': cat_tag,                   # 走勢類別標籤 (預設 "NA")
            'trigger_count': len(w_df),          # 該波段內的總觸發次數
            'c_high_date': c_high_date,           # 1Y 高點日期
            'high_pct': high_pct,                 # 1Y 高點漲幅
            'c_low_date': c_low_date,             # 1Y 低點日期
            'c_low_pct': low_pct,                 # 1Y 低點跌幅
            'h_hold_date': h_hold_date,           # 持倉高點日期
            'h_hold_pct': h_hold_pct,             # 持倉高點漲幅
            'l_hold_date': l_hold_date,           # 持倉低點日期
            'l_hold_pct': l_hold_pct,             # 持倉低點跌幅
            'first_trigger_str': first_trigger_dt.strftime('%Y%m%d'),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'signals': w_df,                      # 該波段所有觸發紀錄
        })

    return waves


def plot_single_wave_chart(wave_info, kline_df, save_path):
    """繪製單一波段 K 線圖，標示波段觸發點、首發走勢分類標籤、1Y 與持倉高低點。"""
    matplotlib.use('Agg')

    plt.rcParams['font.sans-serif'] = [
        'Noto Sans TC',
        'Noto Sans CJK JP',
        'Microsoft JhengHei',
        'DejaVu Sans',
    ]
    plt.rcParams['axes.unicode_minus'] = False

    stock_id = wave_info['stock_id']
    stock_name = wave_info['stock_name']
    signals = wave_info['signals']
    trigger_count = wave_info['trigger_count']
    first_trigger_str = wave_info['first_trigger_str']
    cat_tag = wave_info.get('cat_tag', 'NA') or 'NA'

    s_date = wave_info['start_date']
    e_date = wave_info['end_date']

    df_sub = kline_df.copy()
    stock_col = 'stock_id' if 'stock_id' in df_sub.columns else '股票代號'
    date_col = 'date' if 'date' in df_sub.columns else '日期'

    df_sub[stock_col] = df_sub[stock_col].astype(str)

    df_sub = (
        df_sub[
            (df_sub[date_col] >= s_date)
            & (df_sub[date_col] <= e_date)
            & (df_sub[stock_col] == stock_id)
        ]
        .sort_values(date_col)
        .copy()
    )

    if df_sub.empty:
        return False

    df_sub['DateObj'] = pd.to_datetime(df_sub[date_col])

    col_open = 'open' if 'open' in df_sub.columns else '開盤'
    col_close = 'close' if 'close' in df_sub.columns else '收盤'
    col_high = 'max' if 'max' in df_sub.columns else ('high' if 'high' in df_sub.columns else '最高')
    col_low = 'min' if 'min' in df_sub.columns else ('low' if 'low' in df_sub.columns else '最低')
    col_vol = 'Trading_Volume' if 'Trading_Volume' in df_sub.columns else ('volume' if 'volume' in df_sub.columns else '成交量(張)')

    df_sub = df_sub.reset_index(drop=True)
    x_indices = range(len(df_sub))

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        gridspec_kw={'height_ratios':},
        sharex=True,
    )

    # 主標題帶上走勢類別標籤 (未分類則顯示 【NA】)
    fig.suptitle(
        f'{stock_id} {stock_name} {first_trigger_str} 走勢圖 【{cat_tag}】 (觸發 {trigger_count} 次)',
        fontsize=16,
        fontweight='bold',
        y=0.96,
    )

    # 1. K 線圖繪製
    for idx, row in df_sub.iterrows():
        op, cl, hi, lo = (
            row[col_open],
            row[col_close],
            row[col_high],
            row[col_low],
        )
        color = '#d62728' if cl >= op else '#2ca02c'  # 紅漲綠跌

        ax1.plot([idx, idx], [lo, hi], color=color, linewidth=1.2, zorder=2)
        height = abs(cl - op)
        bottom = min(op, cl)
        rect = patches.Rectangle(
            (idx - 0.35, bottom),
            0.7,
            max(height, 0.05),
            facecolor=color,
            edgecolor=color,
            zorder=3,
        )
        ax1.add_patch(rect)

    # 2. EMA 指數移動平均線與輕鬆線
    ema_configs = [
        ('EMA5', 'EMA5', '#1f77b4', 1.0, '-'),
        ('EMA10', 'EMA10', '#2ca02c', 1.0, '-'),
        ('EMA20', 'EMA20', '#e377c2', 1.2, '-'),
        ('EMA60', 'EMA60 季線', '#ff7f0e', 1.5, '--'),
        ('EMA240', 'EMA240 年線', '#7f7f7f', 1.5, '-.'),
    ]
    for col_name, label_name, color, lw, ls in ema_configs:
        if col_name in df_sub.columns:
            ax1.plot(
                x_indices,
                df_sub[col_name],
                label=label_name,
                color=color,
                linewidth=lw,
                linestyle=ls,
                alpha=0.85,
                zorder=4,
            )

    if 'easy_line' in df_sub.columns:
        ax1.plot(
            x_indices,
            df_sub['easy_line'],
            label='輕鬆線 (easy_line)',
            color='#9467bd',
            linewidth=1.5,
            zorder=4,
        )

    # 3. 標示該波段內【所有觸發日期與價格】 (藍色箭頭 + 文字)
    sig_date_col = '日期' if '日期' in signals.columns else 'date'
    for _, sig_row in signals.iterrows():
        t_date_str = sig_row[sig_date_col]
        t_df = df_sub[df_sub[date_col] == t_date_str]
        if not t_df.empty:
            t_idx = t_df.index
            t_row = t_df.iloc
            t_date_obj = t_row['DateObj']
            t_price = t_row[col_close]
            t_low_p = t_row[col_low]

            ax1.scatter(
                [t_idx], [t_low_p * 0.97], marker='^', color='#1f77b4', s=120, zorder=8
            )
            ax1.annotate(
                f"觸發\n{t_date_obj.strftime('%m/%d')}\n${t_price:.1f}",
                (t_idx, t_low_p * 0.97),
                xytext=(0, -38),
                textcoords='offset points',
                ha='center',
                fontsize=8,
                color='#1f77b4',
                fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=0.9),
                zorder=8,
            )

    # 4. 標示【最高點】 (紅色 Red，置頂圖層 zorder=12 防蓋住)
    high_date_str = wave_info.get('c_high_date')
    high_pct_val = wave_info.get('high_pct', 0.0) or 0.0

    if high_date_str:
        h_df = df_sub[df_sub[date_col] == high_date_str]
        if not h_df.empty:
            h_idx = h_df.index
            h_row = h_df.iloc
            h_price = h_row[col_high]

            ax1.scatter(
                [h_idx],
                [h_price * 1.01],
                marker='v',
                color='#d62728',
                s=140,
                zorder=12,
            )
            ax1.annotate(
                f'★ 最高\n{high_date_str}\n${h_price:.1f} (+{high_pct_val:.1f}%)',
                (h_idx, h_price * 1.01),
                xytext=(0, 24),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#d62728',
                fontweight='bold',
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    facecolor='#ffe6e6',
                    edgecolor='#d62728',
                    alpha=0.95,
                ),
                arrowprops=dict(arrowstyle='->', color='#d62728', lw=1.2),
                zorder=12,
            )

    # 5. 標示【最低點】 (綠色 Green，置頂圖層 zorder=12)
    low_date_str = wave_info.get('c_low_date')
    low_pct_val = wave_info.get('c_low_pct', 0.0) or 0.0

    if low_date_str:
        l_df = df_sub[df_sub[date_col] == low_date_str]
        if not l_df.empty:
            l_idx = l_df.index
            l_row = l_df.iloc
            l_price = l_row[col_low]

            ax1.scatter(
                [l_idx],
                [l_price * 0.99],
                marker='^',
                color='#2ca02c',
                s=140,
                zorder=12,
            )
            ax1.annotate(
                f'▼ 最低\n{low_date_str}\n${l_price:.1f} ({low_pct_val:.1f}%)',
                (l_idx, l_price * 0.99),
                xytext=(0, -44),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#2ca02c',
                fontweight='bold',
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    facecolor='#e6ffe6',
                    edgecolor='#2ca02c',
                    alpha=0.95,
                ),
                arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.2),
                zorder=12,
            )

    # 6. 成交量圖表
    vol_colors = [
        '#d62728' if cl >= op else '#2ca02c'
        for op, cl in zip(df_sub[col_open], df_sub[col_close])
    ]
    ax2.bar(x_indices, df_sub[col_vol], color=vol_colors, alpha=0.7)
    ax2.set_ylabel('成交量', fontsize=10)
    ax2.grid(True, linestyle=':', alpha=0.5)

    ax1.set_ylabel('股價 (TWD)', fontsize=10)
    ax1.grid(True, linestyle=':', alpha=0.5)

    # 7. 圖例與 Y 軸空間調整 (預留 15% 頂部留白，防高點標記蓋住 Legend)
    ax1.legend(loc='lower left', bbox_to_anchor=(0.0, 1.01), ncol=6, frameon=True)

    y_min, y_max = df_sub[col_low].min(), df_sub[col_high].max()
    y_range = y_max - y_min
    ax1.set_ylim(bottom=y_min - y_range * 0.08, top=y_max + y_range * 0.15)

    # 8. 設定 X 軸刻度與日期標籤
    n_ticks = 10
    step = max(1, len(df_sub) // n_ticks)
    tick_positions = list(range(0, len(df_sub), step))
    tick_labels = [
        df_sub.loc[i, 'DateObj'].strftime('%Y-%m') for i in tick_positions
    ]

    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels(tick_labels, rotation=30)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    return True


def generate_qiantang_wave_charts(
    dashboard_df, global_df, output_dir, nas_sftp_path=None
):
    """走勢圖生成與 NAS 備份總控入口."""
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    stock_col = '股票代號' if '股票代號' in dashboard_df.columns else 'stock_id'

    for stock_id, stock_signals in dashboard_df.groupby(stock_col):
        try:
            waves = group_signals_into_waves(stock_signals)
        except Exception as e:
            print(f'⚠ [警告] 股票 {stock_id} 波段歸類失敗: {e}')
            continue

        for wave in waves:
            c_low_pct = wave.get('c_low_pct')
            c_low_date = wave.get('c_low_date')
            c_high_date = wave.get('c_high_date')

            is_pullback_first = (
                c_low_pct is not None
                and c_low_pct <= -10
                and c_low_date is not None
                and c_high_date is not None
                and str(c_low_date) < str(c_high_date)
            )

            if is_pullback_first:
                tag = f'先回檔{c_low_pct}%'
            elif c_low_pct is not None and c_low_pct < -10.0:
                tag = f'後回檔{c_low_pct}%'
            else:
                tag = ''

            tag_str = f'_{tag}' if tag else ''

            # 🌟 1. 取得走勢分類標籤，若未指定或缺失則強制設為 "NA"
            cat_tag = wave.get('cat_tag', 'NA') or 'NA'

            # 🌟 2. 輸出檔名格式：2368_金像電_2368_20230324_Cat1_飆股.png 或 ..._NA.png
            filename = f"{wave['stock_id']}_{wave['stock_name']}_{wave['group_id']}{tag_str}_{cat_tag}.png"
            save_path = os.path.join(output_dir, filename)

            try:
                success = plot_single_wave_chart(wave, global_df, save_path)
                if success:
                    generated_files.append(save_path)
            except Exception as e:
                print(f'⚠ [警告] 繪製走勢圖 {filename} 失敗: {e}')

    return generated_files
