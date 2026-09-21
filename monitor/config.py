# monitor/config.py

DEBUG_VERBOSE = True

PARAM_PROFILES = {
    'TW50': {
        'name': '台灣50',
        'min_vol': 3000000,
        'surge_mult': 0.8,
        # --- 動態比例門檻設定 ---
        'major_sell_ratio': 0.05,       # 主力賣超佔當日成交量 >= 5.0%
        'foreign_sell_ratio': 0.04,     # 外資賣超佔當日成交量 >= 4.0%
        'min_sell_shares': 1500000,        # 保底張數：權值股流動性高，至少需賣滿 1,500 張, 1,500,000股
        'broker_diff': 50,              # 家數差門檻 (買家數 - 賣家數 >= 50，代表籌碼分散至散戶)
    },
    'MID100': {
        'name': '中型100',
        'min_vol': 1500000,
        'surge_mult': 1.0,
        # --- 動態比例門檻設定 ---
        'major_sell_ratio': 0.08,       # 主力賣超佔當日成交量 >= 8.0%
        'foreign_sell_ratio': 0.08,     # 外資賣超佔當日成交量 >= 8.0%
        'min_sell_shares': 500000,         # 保底張數：至少 500 張 (例如神達成交 6 萬張時，自動鎖定門檻為 3,000 張)
        'broker_diff': 30,              # 家數差門檻 (買家數 - 賣家數 >= 30)
    },
    'ICDesign': {
        'name': 'IC設計/高波動',
        'min_vol': 800000,
        'surge_mult': 1.2,
        # --- 動態比例門檻設定 ---
        'major_sell_ratio': 0.04,       # 高價/高波動股籌碼集中，門檻調為 >= 4.0%
        'foreign_sell_ratio': 0.03,     # 外資賣超佔比 >= 3.0%
        'min_sell_shares': 200000,         # 保底張數：高價股總張數少，200 張即具影響力
        'broker_diff': 15,              # 家數差門檻 (買家數 - 賣家數 >= 15)
    },
    'default': {
        'name': '預設族群',
        'min_vol': 1000000,
        'surge_mult': 1.0,
        # --- 動態比例門檻設定 ---
        'major_sell_ratio': 0.05,       # 預設主力賣超佔比 >= 5.0%
        'foreign_sell_ratio': 0.05,     # 預設外資賣超佔比 >= 5.0%
        'min_sell_shares': 300000,         # 一般個股保底 300 張
        'broker_diff': 20,              # 家數差門檻 (買家數 - 賣家數 >= 20)
    }
}
