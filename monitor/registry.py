# 1. 匯入錢塘潮賣訊
from monitor.qiantang_monitor import (
    mon_qiantang_yi_zhu_qing_xiang,       # 一柱清香 (主力強勢鎖碼 / 籌碼高度集中)
    mon_qiantang_dang_tou_bang_he,        # 當頭棒喝 (主力逢高派發 / 籌碼高檔鬆動)
    mon_qiantang_ming_ri_huang_hua,       # 明日黃花 (籌碼退潮派發 / 主力撤退)
    mon_qiantang_tian_nv_san_hua,         # 天女散花 (籌碼高度分散 / 散戶狂接)
    mon_qiantang_xia_shan_meng_hu,         # 下山猛虎 (主力大幅派發 / 賣壓急湧)
    mon_qiantang_da_zhong_xia_ke,         # 打鐘下課 (散戶買超增加 / 籌碼趨於分散)
    mon_qiantang_he_shi,                  # 合十 (多頭籌碼強勢卡位)
    mon_qiantang_ni_diu_ta_jian,          # 你丟他撿 (主力持續派發 / 散戶接盤)
    mon_qiantang_jiang_long_fu_hu,        # 降龍伏虎 (主力大舉洗盤 / 籌碼沉澱)
    mon_qiantang_yuexia_laoren,           # 輕鬆轉空, 月下老人 (技術面/籌碼面轉空訊號)
    mon_qiantang_kd_dead_cross,           # KD 死亡交叉, 可能是地底穿心 (高檔技術面反轉)
    mon_qiantang_didi_chuanxin            # 地底穿心
)

# 2. 匯入自訂賣訊
#from monitor.custom_monitor import (
#    mon_custom_ma_cross,
#)
