# monitor/config.py

DEBUG_VERBOSE = True

PARAM_PROFILES = {
    'TW50': {
        'name': '台灣50',
        'min_vol': 3000,
        'surge_mult': 0.8,
        'major_sell': -2000,     # 主力賣超門檻 (張)
        'foreign_sell': -1500,   # 外資賣超門檻 (張)
        'broker_diff': -50,      # 分點家數差門檻 (買家 - 賣家，負數代表籌碼分散)
    },
    'MID100': {
        'name': '中型100',
        'min_vol': 1500,
        'surge_mult': 1.0,
        'major_sell': -1000,
        'foreign_sell': -800,
        'broker_diff': -30,
    },
    'ICDesign': {
        'name': 'IC設計/高波動',
        'min_vol': 800,
        'surge_mult': 1.2,
        'major_sell': -500,
        'foreign_sell': -300,    # 高價/高波動股外資賣超數百張影響即顯著
        'broker_diff': -15,
    },
    'default': {
        'name': '預設族群',
        'min_vol': 1000,
        'surge_mult': 1.0,
        'major_sell': -800,
        'foreign_sell': -500,
        'broker_diff': -20,
    }
}
