# 1. 匯入錢塘潮賣訊
from monitor.qiantang_monitor import (
    mon_qiantang_yi_zhu_qing_xiang,
    mon_qiantang_dang_tou_bang_he,
    mon_qiantang_ming_ri_huang_hua,
    mon_qiantang_tian_nv_san_hua,
    mon_qiantang_xia_shan_meng_hu,
    mon_qiantang_da_zhong_xia_ke,
    mon_qiantang_he_shi,
    mon_qiantang_ni_diu_wo_jian,
    mon_qiantang_jiang_long_fu_hu,
    mon_qiantang_qing_song_xian_zhuan_kong,
    mon_qiantang_kd_dead_cross,
)

# 2. 匯入自訂賣訊
from monitor.custom_monitor import (
    mon_custom_ma_cross,
)

# ==========================================
# Monitor 總開關字典 (True: 啟用, False: 停用)
# ==========================================
MONITOR_MAP = {
    # --- 錢塘潮 11 大防禦賣訊 ---
    mon_qiantang_yi_zhu_qing_xiang: True,
    mon_qiantang_dang_tou_bang_he: True,
    mon_qiantang_ming_ri_huang_hua: True,
    mon_qiantang_tian_nv_san_hua: True,
    mon_qiantang_xia_shan_meng_hu: True,
    mon_qiantang_da_zhong_xia_ke: True,
    mon_qiantang_he_shi: True,
    mon_qiantang_ni_diu_wo_jian: True,
    mon_qiantang_jiang_long_fu_hu: True,
    mon_qiantang_qing_song_xian_zhuan_kong: True,
    mon_qiantang_kd_dead_cross: True,

    # --- 未來自訂賣訊 ---
    mon_custom_ma_cross: True,
}

# 動態匯出目前啟用的 Monitor 函數清單
ACTIVE_MONITORS = [
    func for func, is_active in MONITOR_MAP.items() if is_active
]
