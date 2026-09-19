# monitor/config.py

PARAM_PROFILES = {
    'tw50': {
        'name': '台灣50',
        'min_vol': 3000,        # 最低有效成交張數
        'surge_mult': 0.8,      # 漲幅過熱/拉高係數
        'major_sell': -2000,    # 主力/外資大賣張數門檻
    },
    'mid100': {
        'name': '中型100',
        'min_vol': 1500,
        'surge_mult': 1.0,
        'major_sell': -1000,
    },
    'ic_design': {
        'name': 'IC設計/高波動',
        'min_vol': 800,
        'surge_mult': 1.2,
        'major_sell': -500,
    },
    'default': {
        'name': '預設族群',
        'min_vol': 1000,
        'surge_mult': 1.0,
        'major_sell': -800,
    }
}
