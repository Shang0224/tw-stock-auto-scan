# utils/wave_chart_generator.py
import os
import re
import shutil
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches

# 設定 Matplotlib 中文字型
plt.rcParams['font.sans-serif'] = ['Noto Sans TC', 'Noto Sans CJK JP', 'Microsoft JhengHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def parse_perf_field(val):
    """
    解析 1Y內最高績效 / 1Y內最低績效 欄位字串。
    支援格式範例:
      - '40.99% (2026-06-03)'
      - '-24.38% $$2026-03-04$$'
      - '1.73% $$2025-08-12$$'
      - '-22.93% (2026-05-18)'
    傳回: (pct_float, date_str)
    """
    if pd.isna(val) or not isinstance(val, str):
        return None, None
    m = re.search(r'([-\d\.]+)%\s*[\(\$]+([\d]{4}-\d{2}-\d{2})[\)\$]+', val)
    if m:
        return float(m.group(1)), m.group(2)
    return None, None


def group_signals_into_waves(stock_df):
    """
    依據《走勢圖繪製規則》對單一股票的所有觸發訊號進行波段歸類 (規則 2, 3, 4)。
    """
    s_df = stock_df.sort_values('日期').copy()
    
    # 解析高低點績效與日期
    high_low_parsed = [parse_perf_field(v) for v in s_df['1Y內最高績效']]
    s_df['high_pct'] = [p[0] for p in high_low_parsed]
    s_df['high_date'] = [p[1] for p in high_low_parsed]
    
    low_parsed = [parse_perf_field(v) for v in s_df['1Y內最低績效']]
    s_df['low_pct'] = [p[0] for p in low_parsed]
    s_df['low_date'] = [p[1] for p in low_parsed]

    processed_indices = set()
    waves = []

    for idx, row in s_df.iterrows():
        if idx in processed_indices:
            continue

        c_high_date = row['high_date']
        c_low_date = row['low_date']
        c_low_pct = row['low_pct']

        matched = [row]
        processed_indices.add(idx)

        for jdx, o_row in s_df.iterrows():
            if jdx in processed_indices:
                continue

            # 規則 2: 高點與低點日期皆相同
            is_rule2 = (o_row['high_date'] == c_high_date) and (o_row['low_date'] == c_low_date)
            
            # 規則 3: 低點日期相同且回檔 > 10% (low_pct <= -10)
            is_rule3 = (o_row['low_date'] == c_low_date) and \
                        (c_low_pct is not None and c_low_pct <= -10) and \
                        (o_row['low_pct'] is not None and o_row['low_pct'] <= -10)
            
            # 規則 4: 高點日期相同且創高回檔 <= 10% (low_pct > -10)
            is_rule4 = (o_row['high_date'] == c_high_date) and \
                        (c_low_pct is not None and c_low_pct > -10) and \
                        (o_row['low_pct'] is not None and o_row['low_pct'] > -10)

            if is_rule2 or is_rule3 or is_rule4:
                matched.append(o_row)
                processed_indices.add(jdx)

        w_df = pd.DataFrame(matched).sort_values('日期')
        first_trigger_dt = pd.to_datetime(w_df['日期'].min())
        last_trigger_dt = pd.to_datetime(w_df['日期'].max())

        # 計算繪圖時間軸 (規則 2, 3, 4 規範)
        if len(w_df) > 1 and w_df['high_date'].nunique() == 1 and w_df['low_date'].nunique() == 1:
            rule_type = "規則2 (標準波段)"
            start_date = first_trigger_dt - pd.DateOffset(months=1)
            end_date = first_trigger_dt + pd.DateOffset(months=13)
        elif c_low_pct is not None and c_low_pct <= -10:
            rule_type = "規則3 (回檔>10%波段)"
            start_date = first_trigger_dt - pd.DateOffset(months=1)
            end_date = last_trigger_dt + pd.DateOffset(months=13)
        else:
            rule_type = "規則4 (創高且回檔<=10%波段)"
            start_date = first_trigger_dt - pd.DateOffset(months=1)
            end_date = last_trigger_dt + pd.DateOffset(months=13)

        waves.append({
            'stock_id': str(row['股票代號']),
            'stock_name': str(row['名稱']),
            'rule_type': rule_type,
            'c_low_pct': c_low_pct,
            'c_low_date': c_low_date,
            'c_high_date': c_high_date,
            'first_trigger_str': first_trigger_dt.strftime('%Y%m%d'),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'signals': w_df
        })

    return waves

def plot_single_wave_chart(wave_info, kline_df, save_path):
    """
    繪製單一波段 K 線圖並標示觸發點(藍箭頭/價格)、紅標高點與綠標低點。
    （使用 EMA 指數移動平均線、移除非交易日與週末空白）
    """
    stock_id = wave_info['stock_id']
    stock_name = wave_info['stock_name']
    signals = wave_info['signals']

    s_date = wave_info['start_date']
    e_date = wave_info['end_date']

    # 確保欄位名稱相符
    df_sub = kline_df.copy()
    if 'stock_id' not in df_sub.columns and '股票代號' in df_sub.columns:
        df_sub['stock_id'] = df_sub['股票代號'].astype(str)
    else:
        df_sub['stock_id'] = df_sub['stock_id'].astype(str)

    if 'date' not in df_sub.columns and '日期' in df_sub.columns:
        df_sub['date'] = df_sub['日期']

    df_sub = df_sub[(df_sub['date'] >= s_date) & (df_sub['date'] <= e_date) & (df_sub['stock_id'] == stock_id)].sort_values('date').copy()

    if df_sub.empty:
        return False

    df_sub['DateObj'] = pd.to_datetime(df_sub['date'])

    # 欄位映射
    col_open = 'open' if 'open' in df_sub.columns else '開盤'
    col_close = 'close' if 'close' in df_sub.columns else '收盤'
    col_high = 'max' if 'max' in df_sub.columns else ('high' if 'high' in df_sub.columns else '最高')
    col_low = 'min' if 'min' in df_sub.columns else ('low' if 'low' in df_sub.columns else '最低')
    col_vol = 'Trading_Volume' if 'Trading_Volume' in df_sub.columns else ('volume' if 'volume' in df_sub.columns else '成交量(張)')

    # 🌟 重置索引為連續整數，消除非交易日/週末在視覺上的空白空隙
    df_sub = df_sub.reset_index(drop=True)
    x_indices = range(len(df_sub))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
    fig.suptitle(f"{stock_id} {stock_name} - 走勢圖 ({wave_info['rule_type']})", fontsize=16, fontweight='bold', y=0.96)

    # 1. K 線圖繪製 (繪製於整數索引位置 idx 上)
    for idx, row in df_sub.iterrows():
        op, cl, hi, lo = row[col_open], row[col_close], row[col_high], row[col_low]
        color = '#d62728' if cl >= op else '#2ca02c'  # 紅漲綠跌 (台股慣例)

        # 上下影線
        ax1.plot([idx, idx], [lo, hi], color=color, linewidth=1.2, zorder=2)
        # 實體 K 棒
        height = abs(cl - op)
        bottom = min(op, cl)
        rect = patches.Rectangle((idx - 0.35, bottom), 0.7, max(height, 0.05),
                                 facecolor=color, edgecolor=color, zorder=3)
        ax1.add_patch(rect)

    # 2. 🌟 EMA 指數移動平均線與輕鬆線 (EMA5, EMA10, EMA20, EMA60, EMA240, 輕鬆線)
    ema_configs = [
        ('EMA5', 'EMA5', '#1f77b4', 1.0, '-'),           # 藍色細線
        ('EMA10', 'EMA10', '#2ca02c', 1.0, '-'),         # 綠色細線
        ('EMA20', 'EMA20', '#e377c2', 1.2, '-'),         # 粉紅線
        ('EMA60', 'EMA60 季線', '#ff7f0e', 1.5, '--'),   # 橘色虛線
        ('EMA240', 'EMA240 年線', '#7f7f7f', 1.5, '-.'), # 灰色點虛線
    ]
    for col_name, label_name, color, lw, ls in ema_configs:
        if col_name in df_sub.columns:
            ax1.plot(x_indices, df_sub[col_name], label=label_name, color=color, linewidth=lw, linestyle=ls, alpha=0.85)

    if 'easy_line' in df_sub.columns:
        ax1.plot(x_indices, df_sub['easy_line'], label='輕鬆線 (easy_line)', color='#9467bd', linewidth=1.5)

    # 3. 標示【觸發日期與價格】 (藍色箭頭 + 文字)
    for _, sig_row in signals.iterrows():
        t_date_str = sig_row['日期']
        t_df = df_sub[df_sub['date'] == t_date_str]
        if not t_df.empty:
            t_idx = t_df.index.item()
            t_row = t_df.iloc[0]
            t_date_obj = t_row['DateObj']
            t_price = t_row[col_close]
            t_low_p = t_row[col_low]

            ax1.scatter([t_idx], [t_low_p * 0.97], marker='^', color='#1f77b4', s=120, zorder=6)
            ax1.annotate(f"觸發\n{t_date_obj.strftime('%m/%d')}\n${t_price:.1f}",
                         (t_idx, t_low_p * 0.97),
                         xytext=(0, -38), textcoords='offset points',
                         ha='center', fontsize=8, color='#1f77b4', fontweight='bold',
                         arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=0.9))

    # 4. 標示【高點日期】 (紅色 Red)
    high_date_str = signals['high_date'] if 'high_date' in signals else None
    high_pct_val = signals['high_pct'] if 'high_pct' in signals else 0.0
    if high_date_str:
        h_df = df_sub[df_sub['date'] == high_date_str]
        if not h_df.empty:
            h_idx = h_df.index.item()
            h_row = h_df.iloc[0]
            h_price = h_row[col_high]

            ax1.scatter([h_idx], [h_price * 1.01], marker='v', color='#d62728', s=140, zorder=7)
            ax1.annotate(f"★ 高點\n{high_date_str}\n${h_price:.1f} (+{high_pct_val:.1f}%)",
                         (h_idx, h_price * 1.01),
                         xytext=(0, 26), textcoords='offset points',
                         ha='center', fontsize=9, color='#d62728', fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffe6e6', edgecolor='#d62728', alpha=0.9),
                         arrowprops=dict(arrowstyle='->', color='#d62728', lw=1.2))

    # 5. 標示【低點日期】 (綠色 Green)
    low_date_str = signals['low_date'] if 'low_date' in signals else None
    low_pct_val = signals['low_pct'] if 'low_pct' in signals else 0.0
    if low_date_str:
        l_df = df_sub[df_sub['date'] == low_date_str]
        if not l_df.empty:
            l_idx = l_df.index.item()
            l_row = l_df.iloc[0]
            l_price = l_row[col_low]

            ax1.scatter([l_idx], [l_price * 0.99], marker='^', color='#2ca02c', s=140, zorder=7)
            ax1.annotate(f"▼ 低點\n{low_date_str}\n${l_price:.1f} ({low_pct_val:.1f}%)",
                         (l_idx, l_price * 0.99),
                         xytext=(0, -44), textcoords='offset points',
                         ha='center', fontsize=9, color='#2ca02c', fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#e6ffe6', edgecolor='#2ca02c', alpha=0.9),
                         arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.2))

    # 6. 成交量圖表 (繪製於整數索引 x_indices 上)
    vol_colors = ['#d62728' if cl >= op else '#2ca02c' for op, cl in zip(df_sub[col_open], df_sub[col_close])]
    ax2.bar(x_indices, df_sub[col_vol], color=vol_colors, alpha=0.7)
    ax2.set_ylabel('成交量', fontsize=10)
    ax2.grid(True, linestyle=':', alpha=0.5)

    ax1.set_ylabel('股價 (TWD)', fontsize=10)
    ax1.grid(True, linestyle=':', alpha=0.5)
    ax1.legend(loc='lower left', bbox_to_anchor=(0.0, 1.01), ncol=6, frameon=True)

    # 7. 🌟 設定 X 軸刻度與日期標籤（均勻選取對應的交易日日期）
    n_ticks = 10
    step = max(1, len(df_sub) // n_ticks)
    tick_positions = list(range(0, len(df_sub), step))
    tick_labels = [df_sub.loc[i, 'DateObj'].strftime('%Y-%m') for i in tick_positions]

    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels(tick_labels, rotation=30)

    plt.tight_layout()

    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    return True


def plot_single_wave_chart_old(wave_info, kline_df, save_path):
    """
    繪製單一波段 K 線圖並標示觸發點(藍箭頭/價格)、紅標高點與綠標低點。
    """
    stock_id = wave_info['stock_id']
    stock_name = wave_info['stock_name']
    signals = wave_info['signals']

    s_date = wave_info['start_date']
    e_date = wave_info['end_date']

    # 確保欄位名稱相符
    df_sub = kline_df.copy()
    if 'stock_id' not in df_sub.columns and '股票代號' in df_sub.columns:
        df_sub['stock_id'] = df_sub['股票代號'].astype(str)
    else:
        df_sub['stock_id'] = df_sub['stock_id'].astype(str)

    if 'date' not in df_sub.columns and '日期' in df_sub.columns:
        df_sub['date'] = df_sub['日期']

    df_sub = df_sub[(df_sub['date'] >= s_date) & (df_sub['date'] <= e_date) & (df_sub['stock_id'] == stock_id)].sort_values('date').copy()

    if df_sub.empty:
        return False

    df_sub['DateObj'] = pd.to_datetime(df_sub['date'])

    # 欄位映射
    col_open = 'open' if 'open' in df_sub.columns else '開盤'
    col_close = 'close' if 'close' in df_sub.columns else '收盤'
    col_high = 'max' if 'max' in df_sub.columns else ('high' if 'high' in df_sub.columns else '最高')
    col_low = 'min' if 'min' in df_sub.columns else ('low' if 'low' in df_sub.columns else '最低')
    col_vol = 'Trading_Volume' if 'Trading_Volume' in df_sub.columns else ('volume' if 'volume' in df_sub.columns else '成交量(張)')

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
    fig.suptitle(f"{stock_id} {stock_name} - 走勢圖 ({wave_info['rule_type']})", fontsize=16, fontweight='bold', y=0.96)

    # 1. K 線圖繪製
    for _, row in df_sub.iterrows():
        d_num = mdates.date2num(row['DateObj'])
        op, cl, hi, lo = row[col_open], row[col_close], row[col_high], row[col_low]
        color = '#d62728' if cl >= op else '#2ca02c' # 紅漲綠跌 (台股慣例)

        ax1.plot([d_num, d_num], [lo, hi], color=color, linewidth=1.2, zorder=2)
        height = abs(cl - op)
        bottom = min(op, cl)
        rect = patches.Rectangle((d_num - 0.35, bottom), 0.7, max(height, 0.05),
                                 facecolor=color, edgecolor=color, zorder=3)
        ax1.add_patch(rect)

    # 2. 均線與輕鬆線 (MA5, MA10, MA20, MA60, MA240, 輕鬆線)
    ma_configs = [
        ('MA5', 'MA5', '#1f77b4', 1.0, '-'),         # 藍色細線
        ('MA10', 'MA10', '#2ca02c', 1.0, '-'),       # 綠色細線
        ('MA20', 'MA20', '#e377c2', 1.2, '-'),       # 粉紅線
        ('MA60', 'MA60 季線', '#ff7f0e', 1.5, '--'), # 橘色虛線
        ('MA240', 'MA240 年線', '#7f7f7f', 1.5, '-.'), # 灰色點虛線
    ]
    for col_name, label_name, color, lw, ls in ma_configs:
        if col_name in df_sub.columns:
            ax1.plot(df_sub['DateObj'], df_sub[col_name], label=label_name, color=color, linewidth=lw, linestyle=ls, alpha=0.85)
    if 'easy_line' in df_sub.columns:
        ax1.plot(df_sub['DateObj'], df_sub['easy_line'], label='輕鬆線 (easy_line)', color='#9467bd', linewidth=1.5)

    # 3. 標示【觸發日期與價格】 (藍色箭頭 + 文字)
    for _, sig_row in signals.iterrows():
        t_date_str = sig_row['日期']
        t_df = df_sub[df_sub['date'] == t_date_str]
        if not t_df.empty:
            t_row = t_df.iloc[0]
            t_date_obj = t_row['DateObj']
            t_price = t_row[col_close]
            t_low_p = t_row[col_low]

            ax1.scatter([t_date_obj], [t_low_p * 0.97], marker='^', color='#1f77b4', s=120, zorder=6)
            ax1.annotate(f"觸發\n{t_date_obj.strftime('%m/%d')}\n${t_price:.1f}",
                         (t_date_obj, t_low_p * 0.97),
                         xytext=(0, -38), textcoords='offset points',
                         ha='center', fontsize=8, color='#1f77b4', fontweight='bold',
                         arrowprops=dict(arrowstyle='->', color='#1f77b4', lw=0.9))

    # 4. 標示【高點日期】 (紅色 Red)
    high_date_str = signals.iloc[0]['high_date']
    high_pct_val = signals.iloc[0]['high_pct']
    if high_date_str:
        h_df = df_sub[df_sub['date'] == high_date_str]
        if not h_df.empty:
            h_row = h_df.iloc[0]
            h_date_obj = h_row['DateObj']
            h_price = h_row[col_high]

            ax1.scatter([h_date_obj], [h_price * 1.01], marker='v', color='#d62728', s=140, zorder=7)
            ax1.annotate(f"★ 高點\n{high_date_str}\n${h_price:.1f} (+{high_pct_val:.1f}%)",
                         (h_date_obj, h_price * 1.01),
                         xytext=(0, 26), textcoords='offset points',
                         ha='center', fontsize=9, color='#d62728', fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#ffe6e6', edgecolor='#d62728', alpha=0.9),
                         arrowprops=dict(arrowstyle='->', color='#d62728', lw=1.2))

    # 5. 標示【低點日期】 (綠色 Green)
    low_date_str = signals.iloc[0]['low_date']
    low_pct_val = signals.iloc[0]['low_pct']
    if low_date_str:
        l_df = df_sub[df_sub['date'] == low_date_str]
        if not l_df.empty:
            l_row = l_df.iloc[0]
            l_date_obj = l_row['DateObj']
            l_price = l_row[col_low]

            ax1.scatter([l_date_obj], [l_price * 0.99], marker='^', color='#2ca02c', s=140, zorder=7)
            ax1.annotate(f"▼ 低點\n{low_date_str}\n${l_price:.1f} ({low_pct_val:.1f}%)",
                         (l_date_obj, l_price * 0.99),
                         xytext=(0, -44), textcoords='offset points',
                         ha='center', fontsize=9, color='#2ca02c', fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.3', facecolor='#e6ffe6', edgecolor='#2ca02c', alpha=0.9),
                         arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.2))

    # 6. 成交量圖表
    vol_colors = ['#d62728' if cl >= op else '#2ca02c' for op, cl in zip(df_sub[col_open], df_sub[col_close])]
    ax2.bar(df_sub['DateObj'], df_sub[col_vol], color=vol_colors, alpha=0.7)
    ax2.set_ylabel('成交量', fontsize=10)
    ax2.grid(True, linestyle=':', alpha=0.5)

    ax1.set_ylabel('股價 (TWD)', fontsize=10)
    ax1.grid(True, linestyle=':', alpha=0.5)
    #ax1.legend(loc='upper left', frameon=True)
    # 🌟 修改後：橫向平鋪於圖表上方外側 (完全不遮擋 K 線資料)
    ax1.legend(
        loc='lower left', bbox_to_anchor=(0.0, 1.01), ncol=6, frameon=True
    )

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    plt.xticks(rotation=30)
    plt.tight_layout()

    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    return True


def ensure_remote_sftp_dir(remote_dir_path):
    """
    連結 NAS SFTP 並直接嘗試建立遠端資料夾層級 (完全不進行事先 stat 檢查/判斷)
    """
    try:
        import paramiko
    except ImportError:
        print("⚠ 未安裝 paramiko，無法自動建立 SFTP 遠端目錄")
        return

    host = os.getenv('NAS_VPN_IP')
    port = int(os.getenv('NAS_SFTP_PORT', 22))
    username = os.getenv('NAS_ACCOUNT')
    password = os.getenv('NAS_PASSWORD')

    if not all([host, username, password]):
        print("⚠ 缺少 NAS SFTP 連線設定 (NAS_VPN_IP / NAS_ACCOUNT / NAS_PASSWORD)")
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
                print(f"📁 [SFTP] 已直接建立遠端資料夾：{current_path}")
            except Exception:
                pass

        sftp.close()
    except Exception as e:
        print(f"⚠ 自動建立 NAS 遠端目錄連線提醒: {e}")
    finally:
        try:
            ssh.close()
        except Exception:
            pass


def generate_qiantang_wave_charts(dashboard_df, global_df, output_dir, nas_sftp_path=None):
    """
    走勢圖生成與 NAS 備份總控入口。
    檔名命名規則：當觸發後「1年內最低績效 <= -10%」且「低點日期早於高點日期 (比1年新高先出來)」時，檔名會包含「先回檔走勢圖」。
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    for stock_id, stock_signals in dashboard_df.groupby('股票代號'):
        waves = group_signals_into_waves(stock_signals)

        for wave in waves:
            # 🌟 判斷條件：
            # 1. 1Y 內最低績效 <= -10%
            # 2. 1Y 低點日期早於 1Y 高點日期 (低點比高點先出來)
            c_low_pct = wave.get('c_low_pct')
            c_low_date = wave.get('c_low_date')
            c_high_date = wave.get('c_high_date')

            is_pullback_first = (
                c_low_pct is not None and c_low_pct <= -10 and
                c_low_date is not None and c_high_date is not None and
                str(c_low_date) < str(c_high_date)
            )

            #tag = f"先回檔{c_low_pct}" if is_pullback_first else ""
            # 依據條件設定對應的 tag
            if is_pullback_first:
                tag = f"先回檔{c_low_pct}%"
            elif c_low_pct < -10.0:
                tag = f"後回檔{c_low_pct}%"
            else:
                tag = ""

            filename = f"{wave['stock_id']}_{wave['stock_name']}_{wave['first_trigger_str']}_{tag}走勢圖.png"
            save_path = os.path.join(output_dir, filename)

            success = plot_single_wave_chart(wave, global_df, save_path)
            if success:
                generated_files.append(save_path)

    # 若傳入 NAS SFTP 路徑，直接建立遠端目錄，再逐一推送圖片至 NAS
    if nas_sftp_path and generated_files:
        folder_name = os.path.basename(os.path.normpath(output_dir))
        target_nas_dir = f"{nas_sftp_path.rstrip('/')}/{folder_name}"

        ensure_remote_sftp_dir(target_nas_dir)

        try:
            from utils import archive_and_cleanup
            success_count = 0
            for img_path in generated_files:
                fname = os.path.basename(img_path)
                remote_img_path = f"{target_nas_dir}/{fname}"
                archive_and_cleanup(img_path, remote_img_path)
                success_count += 1
            print(f"☁️ [純 SFTP 上傳] 已成功同步上傳 {success_count} 張走勢圖至 NAS: {target_nas_dir}")
        except Exception as e:
            print(f"⚠ 走勢圖 NAS SFTP 備份失敗: {e}")

    return generated_files

