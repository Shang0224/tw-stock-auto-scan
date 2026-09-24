# strategy/__init__.py
from strategy.qiantang_strategies import (
    st_qiantang_f1_spt_growth,
    st_qiantang_f2_volume_breakout,
    st_qiantang_f3_after_shakeout,
    st_qiantang_f4_strong_rise,
    st_qiantang_f5_major_buy_easy,
    st_qiantang_f6_flower,
    st_qiantang_f7_super_stock,
)

# 7 大多方選股預設全集清單
ALL_QIANTANG_LONG_STRATEGIES = [
    st_qiantang_f1_spt_growth,
    st_qiantang_f2_volume_breakout,
    st_qiantang_f3_after_shakeout,
    st_qiantang_f4_strong_rise,
    st_qiantang_f5_major_buy_easy,
    st_qiantang_f6_flower,
    st_qiantang_f7_super_stock,
]
