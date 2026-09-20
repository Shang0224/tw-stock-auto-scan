# monitor/config.py

PARAM_PROFILES = {
    'TW50': {
        'name': '台灣50',
        'min_vol': 3000,
        'surge_mult': 0.8,
        'major_sell': -2000,
    },
    'MID100': {
        'name': '中型100',
        'min_vol': 1500,
        'surge_mult': 1.0,
        'major_sell': -1000,
    },
    'ICDesign': {
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
