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
    """解析 1Y內最高績效 / 1Y內最低績效 欄位字串。

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
    """依據『波段群組編號』對單一股票的所有觸發訊號進行精準波段歸類。"""
    s_df = stock_df.sort_values('日期').copy()
    waves = []

    # 🌟 直接依據系統固定產出的【波段群組編號】進行分組
    for wave_id, w_df in s_df.groupby('波段群組編號', sort=False):
        w_df = w_df.sort_values('日期')
        first_row = w_df.iloc[0]

        # 🌟 直接解析固定的極值欄位
        high_pct, c_high_date = parse_perf_field(first_row['1Y內最高績效'])
        low_pct, c_low_date = parse_perf_field(first_row['1Y內最低績效'])

        first_trigger_dt = pd.to_datetime(w_df['日期'].min())
        last_trigger_dt = pd.to_datetime(w_df['日期'].max())

        start_date = first_trigger_dt - pd.DateOffset(months=1)
        end_date = last_trigger_dt + pd.DateOffset(months=13)

        waves.append({
            'stock_id': str(first_row['股票代號']),
            'stock_name': str(first_row['名稱']),
            'group_id': str(wave_id),
            'trigger_count': len(w_df),  # 該波段內的總觸發次數
            'c_low_pct': low_pct,
            'c_low_date': c_low_date,
            'c_high_date': c_high_date,
            'high_pct': high_pct,
            'first_trigger_str': first_trigger_dt.strftime('%Y%m%d'),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'signals': w_df,  # 包含該波段所有觸發點 (圖上繪製藍箭頭)
        })

    return waves


def plot_single_wave_chart(wave_info, kline_df, save_path):
    """繪製單一波段 K 線圖並標示波段內所有觸發點(藍箭頭/價格)、高點與低點。"""
    matplotlib.use('Agg')

    # 設定 Matplotlib 中文字型
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

    s_date = wave_info['start_date']
    e_date = wave_info['end_date']

    # 切割對應股票與時間區間的 K 線資料
    df_sub = (
        kline_df[
            (kline_df['date'] >= s_date)
            & (kline_df['date'] <= e_date)
            & (kline_df['stock_id'] == stock_id)
        ]
        .sort_values('date')
        .copy()
    )

    if df_sub.empty:
        return False

    df_sub['DateObj'] = pd.to_datetime(df_sub['date'])

    # 重置索引為連續整數，消除非交易日/週末在視覺上的空白空隙
    df_sub = df_sub.reset_index(drop=True)
    x_indices = range(len(df_sub))

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        gridspec_kw={'height_ratios': [3, 1]},
        sharex=True,
    )

    # 主標題：呈現股票資訊、首發日期與觸發次數
    fig.suptitle(
        f'{stock_id} {stock_name} {first_trigger_str} 走勢圖 (觸發 {trigger_count} 次)',
        fontsize=16,
        fontweight='bold',
        y=0.96,
    )

    # 1. K 線圖繪製
    for idx, row in df_sub.iterrows():
        op, cl, hi, lo = (
            row['open'],
            row['close'],
            row['max'],
            row['min'],
        )
        color = '#d62728' if cl >= op else '#2ca02c'  # 紅漲綠跌 (台股慣例)

        # 上下影線
        ax1.plot([idx, idx], [lo, hi], color=color, linewidth=1.2, zorder=2)
        # 實體 K 棒
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
        ('EMA5', 'EMA5', '#1f77b4', 1.0, '-'),  # 藍色細線
        ('EMA10', 'EMA10', '#2ca02c', 1.0, '-'),  # 綠色細線
        ('EMA20', 'EMA20', '#e377c2', 1.2, '-'),  # 粉紅線
        ('EMA60', 'EMA60 季線', '#ff7f0e', 1.5, '--'),  # 橘色虛線
        ('EMA240', 'EMA240 年線', '#7f7f7f', 1.5, '-.'),  # 灰色點虛線
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
            )

    if 'easy_line' in df_sub.columns:
        ax1.plot(
            x_indices,
            df_sub['easy_line'],
            label='輕鬆線 (easy_line)',
            color='#9467bd',
            linewidth=1.5,
        )

    # 3. 標示該波段內【所有觸發日期與價格】 (藍色箭頭 + 文字)
    for _, sig_row in signals.iterrows():
        t_date_str = sig_row['日期']
        t_df = df_sub[df_sub['date'] == t_date_str]
        if not t_df.empty:
            t_idx = t_df.index[0]
            t_row = t_df.iloc[0]
            t_date_obj = t_row['DateObj']
            t_price = t_row['close']
            t_low_p = t_row['min']

            ax1.scatter(
                [t_idx], [t_low_p * 0.97], marker='^', color='#1f77b4', s=120, zorder=6
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
            )

    # 4. 取得高低點資訊
    high_date_str = wave_info.get('c_high_date')
    low_date_str = wave_info.get('c_low_date')

    high_pct_val = wave_info.get('high_pct', 0.0) or 0.0
    low_pct_val = wave_info.get('c_low_pct', 0.0) or 0.0

    # 5. 標示【高點日期】 (紅色 Red)
    if high_date_str:
        h_df = df_sub[df_sub['date'] == high_date_str]
        if not h_df.empty:
            h_idx = h_df.index[0]
            h_row = h_df.iloc[0]
            h_price = h_row['max']

            ax1.scatter(
                [h_idx],
                [h_price * 1.01],
                marker='v',
                color='#d62728',
                s=140,
                zorder=7,
            )
            ax1.annotate(
                f'★ 高點\n{high_date_str}\n${h_price:.1f} (+{high_pct_val:.1f}%)',
                (h_idx, h_price * 1.01),
                xytext=(0, 26),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#d62728',
                fontweight='bold',
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    facecolor='#ffe6e6',
                    edgecolor='#d62728',
                    alpha=0.9,
                ),
                arrowprops=dict(arrowstyle='->', color='#d62728', lw=1.2),
            )

    # 6. 標示【低點日期】 (綠色 Green)
    if low_date_str:
        l_df = df_sub[df_sub['date'] == low_date_str]
        if not l_df.empty:
            l_idx = l_df.index[0]
            l_row = l_df.iloc[0]
            l_price = l_row['min']

            ax1.scatter(
                [l_idx],
                [l_price * 0.99],
                marker='^',
                color='#2ca02c',
                s=140,
                zorder=7,
            )
            ax1.annotate(
                f'▼ 低點\n{low_date_str}\n${l_price:.1f} ({low_pct_val:.1f}%)',
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
                    alpha=0.9,
                ),
                arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.2),
            )

    # 7. 成交量圖表
    vol_colors = [
        '#d62728' if cl >= op else '#2ca02c'
        for op, cl in zip(df_sub['open'], df_sub['close'])
    ]
    ax2.bar(x_indices, df_sub['Trading_Volume'], color=vol_colors, alpha=0.7)
    ax2.set_ylabel('成交量', fontsize=10)
    ax2.grid(True, linestyle=':', alpha=0.5)

    ax1.set_ylabel('股價 (TWD)', fontsize=10)
    ax1.grid(True, linestyle=':', alpha=0.5)
    ax1.legend(loc='lower left', bbox_to_anchor=(0.0, 1.01), ncol=6, frameon=True)

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


def ensure_remote_sftp_dir(remote_dir_path):
    """連結 NAS SFTP 並直接嘗試建立遠端資料夾層級."""
    try:
        import paramiko
    except ImportError:
        print('⚠ 未安裝 paramiko，無法自動建立 SFTP 遠端目錄')
        return

    host = os.getenv('NAS_VPN_IP')
    port = int(os.getenv('NAS_SFTP_PORT', 22))
    username = os.getenv('NAS_ACCOUNT')
    password = os.getenv('NAS_PASSWORD')

    if not all([host, username, password]):
        print('⚠ 缺少 NAS SFTP 連線設定 (NAS_VPN_IP / NAS_ACCOUNT / NAS_PASSWORD)')
        return

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, port=port, username=username, password=password, timeout=10)
        sftp = ssh.open_sftp()

        parts = remote_dir_path.strip('/').split('/')
        current_path = ''
        for part in parts:
            if not part:
                continue
            current_path += f'/{part}'
            try:
                sftp.mkdir(current_path)
                print(f'📁 [SFTP] 已直接建立遠端資料夾：{current_path}')
            except Exception:
                pass

        sftp.close()
    except Exception as e:
        print(f'⚠ 自動建立 NAS 遠端目錄連線提醒: {e}')
    finally:
        try:
            ssh.close()
        except Exception:
            pass


def generate_qiantang_wave_charts(
    dashboard_df, global_df, output_dir, nas_sftp_path=None
):
    """走勢圖生成與 NAS 備份總控入口."""
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    for stock_id, stock_signals in dashboard_df.groupby('股票代號'):
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
            filename = f"{wave['stock_id']}_{wave['stock_name']}_{wave['group_id']}{tag_str}_走勢圖.png"
            save_path = os.path.join(output_dir, filename)

            try:
                success = plot_single_wave_chart(wave, global_df, save_path)
                if success:
                    generated_files.append(save_path)
            except Exception as e:
                print(f'⚠ [警告] 繪製走勢圖 {filename} 失敗: {e}')

    # 若傳入 NAS SFTP 路徑，逐一推送圖片至 NAS
    if nas_sftp_path and generated_files:
        folder_name = os.path.basename(os.path.normpath(output_dir))
        target_nas_dir = f"{nas_sftp_path.rstrip('/')}/{folder_name}"

        ensure_remote_sftp_dir(target_nas_dir)

        try:
            from utils import archive_and_cleanup

            success_count = 0
            for img_path in generated_files:
                fname = os.path.basename(img_path)
                remote_img_path = f'{target_nas_dir}/{fname}'
                archive_and_cleanup(img_path, remote_img_path)
                success_count += 1
            print(
                '☁️ [純 SFTP 上傳] 已成功同步上傳'
                f' {success_count} 張走勢圖至 NAS: {target_nas_dir}'
            )
        except Exception as e:
            print(f'⚠ 走勢圖 NAS SFTP 備份失敗: {e}')

    return generated_files
