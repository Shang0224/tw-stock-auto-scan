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
    """解析 1Y內最高績效 / 持倉最高績效 / 1Y內最低績效 / 持倉實際最低績效 欄位字串。"""
    if pd.isna(val) or not isinstance(val, str):
        return None, None
    m = re.search(r'([+\-\d.]+)%\s*[\(\$]+([\d]{4}-\d{2}-\d{2})', val)
    if m:
        return float(m.group(1)), m.group(2)
    return None, None


def group_signals_into_waves(stock_df):
    """依據『波段群組編號』對單一股票的所有觸發訊號進行精準波段歸類，並擷取首發標籤與極值。"""
    s_df = stock_df.sort_values('日期').copy()

    if '波段群組編號' not in s_df.columns:
        from utils.analytics import calculate_wave_dedup_info
        records = calculate_wave_dedup_info(s_df.to_dict('records'))
        s_df = pd.DataFrame(records).sort_values('日期')

    waves = []

    for wave_id, w_df in s_df.groupby('波段群組編號', sort=False):
        w_df = w_df.sort_values('日期')
        first_row = w_df.iloc[0]

        raw_cat = first_row.get('走勢類別標籤', 'NA')
        cat_tag = str(raw_cat).strip() if (pd.notna(raw_cat) and str(raw_cat).strip()) else 'NA'

        high_pct, c_high_date = parse_perf_field(first_row.get('1Y內最高績效', ''))
        low_pct, c_low_date = parse_perf_field(first_row.get('1Y內最低績效', ''))

        h_hold_pct, h_hold_date = parse_perf_field(first_row.get('持倉最高績效', ''))
        l_hold_pct, l_hold_date = parse_perf_field(first_row.get('持倉實際最低績效', ''))

        first_trigger_dt = pd.to_datetime(w_df['日期'].min())
        last_trigger_dt = pd.to_datetime(w_df['日期'].max())

        start_date = first_trigger_dt - pd.DateOffset(months=1)
        end_date = last_trigger_dt + pd.DateOffset(months=13)

        waves.append({
            'stock_id': str(first_row['股票代號']),
            'stock_name': str(first_row['名稱']),
            'group_id': str(wave_id),
            'cat_tag': cat_tag,
            'trigger_count': len(w_df),
            'c_high_date': c_high_date,
            'high_pct': high_pct,
            'c_low_date': c_low_date,
            'c_low_pct': low_pct,
            'h_hold_date': h_hold_date,
            'h_hold_pct': h_hold_pct,
            'l_hold_date': l_hold_date,
            'l_hold_pct': l_hold_pct,
            'first_trigger_str': first_trigger_dt.strftime('%Y%m%d'),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'signals': w_df,
        })

    return waves


def plot_single_wave_chart(wave_info, kline_df, save_path):
    """繪製單一波段 K 線圖，智慧避避高低點、持倉極值與觸發點標籤重疊。"""
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
        gridspec_kw={'height_ratios': [3, 1]},
        sharex=True,
    )

    fig.suptitle(
        f'{stock_id} {stock_name} {first_trigger_str} 走勢圖 【{cat_tag}】 (觸發 {trigger_count} 次)',
        fontsize=16,
        fontweight='bold',
        y=0.96,
    )

    # 1. K 線圖繪製
    for idx, row in df_sub.iterrows():
        op, cl, hi, lo = row[col_open], row[col_close], row[col_high], row[col_low]
        color = '#d62728' if cl >= op else '#2ca02c'

        ax1.plot([idx, idx], [lo, hi], color=color, linewidth=1.2, zorder=2)
        height = abs(cl - op)
        bottom = min(op, cl)
        rect = patches.Rectangle(
            (idx - 0.35, bottom), 0.7, max(height, 0.05), facecolor=color, edgecolor=color, zorder=3
        )
        ax1.add_patch(rect)

    # 2. EMA 均線
    ema_configs = [
        ('EMA5', 'EMA5', '#1f77b4', 1.0, '-'),
        ('EMA10', 'EMA10', '#2ca02c', 1.0, '-'),
        ('EMA20', 'EMA20', '#e377c2', 1.2, '-'),
        ('EMA60', 'EMA60 季線', '#ff7f0e', 1.5, '--'),
        ('EMA240', 'EMA240 年線', '#7f7f7f', 1.5, '-.'),
    ]
    for col_name, label_name, color, lw, ls in ema_configs:
        if col_name in df_sub.columns:
            ax1.plot(x_indices, df_sub[col_name], label=label_name, color=color, linewidth=lw, linestyle=ls, alpha=0.85, zorder=4)

    if 'easy_line' in df_sub.columns:
        ax1.plot(x_indices, df_sub['easy_line'], label='輕鬆線 (easy_line)', color='#9467bd', linewidth=1.5, zorder=4)

    # 3. 標示波段內所有觸發點，並記錄觸發點的 K 棒索引位置 (用於避讓低點標籤)
    sig_date_col = '日期' if '日期' in signals.columns else 'date'
    trigger_indices = set()

    for _, sig_row in signals.iterrows():
        t_date_str = sig_row[sig_date_col]
        t_df = df_sub[df_sub[date_col] == t_date_str]
        if not t_df.empty:
            t_idx = t_df.index[0]
            trigger_indices.add(t_idx)
            t_row = t_df.iloc[0]
            t_date_obj = t_row['DateObj']
            t_price = t_row[col_close]
            t_low_p = t_row[col_low]

            ax1.scatter([t_idx], [t_low_p * 0.97], marker='^', color='#1f77b4', s=120, zorder=8)
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

    # 4. 智慧高點標示
    c_high_date = wave_info.get('c_high_date')
    high_pct = wave_info.get('high_pct', 0.0) or 0.0
    h_hold_date = wave_info.get('h_hold_date')
    h_hold_pct = wave_info.get('h_hold_pct', 0.0) or 0.0

    if c_high_date and h_hold_date and c_high_date == h_hold_date:
        h_df = df_sub[df_sub[date_col] == c_high_date]
        if not h_df.empty:
            h_idx = h_df.index[0]
            h_price = h_df.iloc[0][col_high]
            ax1.scatter([h_idx], [h_price * 1.01], marker='v', color='#d62728', s=140, zorder=12)
            ax1.annotate(
                f'★ 1Y/持倉最高\n{c_high_date}\n${h_price:.1f} (+{high_pct:.1f}%)',
                (h_idx, h_price * 1.01),
                xytext=(0, 24),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#d62728',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffe6e6', edgecolor='#d62728', alpha=0.95),
                arrowprops=dict(arrowstyle='->', color='#d62728', lw=1.2),
                zorder=12,
            )
    else:
        h1_idx, h2_idx = None, None
        if c_high_date:
            df1 = df_sub[df_sub[date_col] == c_high_date]
            if not df1.empty: h1_idx = df1.index[0]
        if h_hold_date:
            df2 = df_sub[df_sub[date_col] == h_hold_date]
            if not df2.empty: h2_idx = df2.index[0]

        is_close_h = (h1_idx is not None and h2_idx is not None and abs(h1_idx - h2_idx) < 10)

        if h1_idx is not None:
            h_price = df_sub.loc[h1_idx, col_high]
            offset_y = 48 if (is_close_h and h1_idx > h2_idx) else 24
            ax1.scatter([h1_idx], [h_price * 1.01], marker='v', color='#d62728', s=140, zorder=12)
            ax1.annotate(
                f'★ 1Y最高\n{c_high_date}\n${h_price:.1f} (+{high_pct:.1f}%)',
                (h1_idx, h_price * 1.01),
                xytext=(0, offset_y),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#d62728',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffe6e6', edgecolor='#d62728', alpha=0.95),
                arrowprops=dict(arrowstyle='->', color='#d62728', lw=1.2),
                zorder=12,
            )

        if h2_idx is not None:
            h_price = df_sub.loc[h2_idx, col_high]
            offset_y = 48 if (is_close_h and h2_idx >= h1_idx) else 24
            ax1.scatter([h2_idx], [h_price * 1.01], marker='v', color='#b22222', s=120, zorder=12)
            ax1.annotate(
                f'★ 持倉最高\n{h_hold_date}\n${h_price:.1f} (+{h_hold_pct:.1f}%)',
                (h2_idx, h_price * 1.01),
                xytext=(0, offset_y),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#b22222',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff0f0', edgecolor='#b22222', alpha=0.95),
                arrowprops=dict(arrowstyle='->', color='#b22222', lw=1.2),
                zorder=12,
            )

    # 🌟 5. 智慧低點標示 (含觸發點碰撞避讓：若與藍色觸發點同日或相距≤2天，低點標籤自動往下移至 -78)
    c_low_date = wave_info.get('c_low_date')
    low_pct = wave_info.get('c_low_pct', 0.0) or 0.0
    l_hold_date = wave_info.get('l_hold_date')
    l_hold_pct = wave_info.get('l_hold_pct', 0.0) or 0.0

    if c_low_date and l_hold_date and c_low_date == l_hold_date:
        l_df = df_sub[df_sub[date_col] == c_low_date]
        if not l_df.empty:
            l_idx = l_df.index[0]
            l_price = l_df.iloc[0][col_low]
            # 🌟 檢查是否與任何觸發點碰撞
            has_trigger_collide = any(abs(l_idx - ti) <= 2 for ti in trigger_indices)
            offset_y = -78 if has_trigger_collide else -44

            ax1.scatter([l_idx], [l_price * 0.99], marker='^', color='#2ca02c', s=140, zorder=12)
            ax1.annotate(
                f'▼ 1Y/持倉最低\n{c_low_date}\n${l_price:.1f} ({low_pct:.1f}%)',
                (l_idx, l_price * 0.99),
                xytext=(0, offset_y),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#2ca02c',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#e6ffe6', edgecolor='#2ca02c', alpha=0.95),
                arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.2),
                zorder=12,
            )
    else:
        l1_idx, l2_idx = None, None
        if c_low_date:
            df1 = df_sub[df_sub[date_col] == c_low_date]
            if not df1.empty: l1_idx = df1.index[0]
        if l_hold_date:
            df2 = df_sub[df_sub[date_col] == l_hold_date]
            if not df2.empty: l2_idx = df2.index[0]

        is_close_l = (l1_idx is not None and l2_idx is not None and abs(l1_idx - l2_idx) < 10)

        if l1_idx is not None:
            l_price = df_sub.loc[l1_idx, col_low]
            has_trigger_collide = any(abs(l1_idx - ti) <= 2 for ti in trigger_indices)
            base_offset = -78 if has_trigger_collide else -44
            offset_y = (base_offset - 24) if (is_close_l and l1_idx > l2_idx) else base_offset

            ax1.scatter([l1_idx], [l_price * 0.99], marker='^', color='#2ca02c', s=140, zorder=12)
            ax1.annotate(
                f'▼ 1Y最低\n{c_low_date}\n${l_price:.1f} ({low_pct:.1f}%)',
                (l1_idx, l_price * 0.99),
                xytext=(0, offset_y),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#2ca02c',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#e6ffe6', edgecolor='#2ca02c', alpha=0.95),
                arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.2),
                zorder=12,
            )

        if l2_idx is not None:
            l_price = df_sub.loc[l2_idx, col_low]
            has_trigger_collide = any(abs(l2_idx - ti) <= 2 for ti in trigger_indices)
            base_offset = -78 if has_trigger_collide else -44
            offset_y = (base_offset - 24) if (is_close_l and l2_idx >= l1_idx) else base_offset

            ax1.scatter([l2_idx], [l_price * 0.99], marker='^', color='#006400', s=120, zorder=12)
            ax1.annotate(
                f'▼ 持倉最低\n{l_hold_date}\n${l_price:.1f} ({l_hold_pct:.1f}%)',
                (l2_idx, l_price * 0.99),
                xytext=(0, offset_y),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                color='#006400',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#f0fff0', edgecolor='#006400', alpha=0.95),
                arrowprops=dict(arrowstyle='->', color='#006400', lw=1.2),
                zorder=12,
            )

    # 6. 成交量圖表
    vol_colors = ['#d62728' if cl >= op else '#2ca02c' for op, cl in zip(df_sub[col_open], df_sub[col_close])]
    ax2.bar(x_indices, df_sub[col_vol], color=vol_colors, alpha=0.7)
    ax2.set_ylabel('成交量', fontsize=10)
    ax2.grid(True, linestyle=':', alpha=0.5)

    ax1.set_ylabel('股價 (TWD)', fontsize=10)
    ax1.grid(True, linestyle=':', alpha=0.5)

    # 7. 圖例與 Y 軸空間調整 (頂部留白 18%，底部留白 15% 確保下方的藍色觸發框與綠色最低框完全容納)
    ax1.legend(loc='lower left', bbox_to_anchor=(0.0, 1.01), ncol=6, frameon=True)

    y_min, y_max = df_sub[col_low].min(), df_sub[col_high].max()
    y_range = y_max - y_min
    ax1.set_ylim(bottom=y_min - y_range * 0.15, top=y_max + y_range * 0.18)

    # 8. X 軸刻度設定
    n_ticks = 10
    step = max(1, len(df_sub) // n_ticks)
    tick_positions = list(range(0, len(df_sub), step))
    tick_labels = [df_sub.loc[i, 'DateObj'].strftime('%Y-%m') for i in tick_positions]

    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels(tick_labels, rotation=30)

    plt.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    return True


def ensure_remote_sftp_dir(remote_dir_path):
    """連結 NAS SFTP 並嘗試建立遠端目錄層級."""
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

            cat_tag = wave.get('cat_tag', 'NA') or 'NA'
            filename = f"{wave['stock_id']}_{wave['stock_name']}_{wave['group_id']}{tag_str}_{cat_tag}.png"
            save_path = os.path.join(output_dir, filename)

            try:
                success = plot_single_wave_chart(wave, global_df, save_path)
                if success:
                    generated_files.append(save_path)
            except Exception as e:
                print(f'⚠ [警告] 繪製走勢圖 {filename} 失敗: {e}')

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
