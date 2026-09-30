# strategy/config.py

DEBUG_VERBOSE = True

PARAM_PROFILES = {
    'TW50': {
        'name': '台灣50',
        'min_vol': 3000 * 1000,                  # 👈 各策略共用的最低張數門檻（3,000 張）
        # 專屬於各策略的參數子集合
        'f2_volume_breakout': {
            'surge_mult': 0.8,                   # 爆量倍數動態調節係數
            'min_price': 5.0,                    # 最低收盤價限制
        }
    },
    'MID100': {
        'name': '中型100',
        'min_vol': 1500 * 1000,                  # 👈 1,500 張
        'f2_volume_breakout': {
            'surge_mult': 1.0,                   # 標準倍數
            'min_price': 5.0,                    # 最低收盤價限制
        }
    },
    'ICDesign': {
        'name': 'IC設計/高波動',
        'min_vol': 800 * 1000,                   # 👈 800 張
        'f2_volume_breakout': {
            'surge_mult': 1.2,                   # 提高爆量要求標準
            'min_price': 5.0,                    # 最低收盤價限制
        }
    },
    'default': {
        'name': '預設族群',
        'min_vol': 1000 * 1000,                  # 👈 1,000 張
        'f2_volume_breakout': {
            'surge_mult': 1.0,                   # 標準倍數
            'min_price': 5.0,                    # 最低收盤價限制
        }
    }
}
