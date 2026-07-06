# utils/__init__.py

# 把各個子檔案的精華函式拉進來
from utils.data_fetcher import yf_fetch_all_stocks, fm_fetch_all_stocks
from utils.notifier import send_line_message, send_email_with_csv
from utils.storage import upload_to_nas
from utils.file_handler import parse_stock_ids, get_stock_name_dict, send_report, cleanup_local_file

# 這行定義了當別人寫 from utils import * 時，允許拿走哪些東西
__all__ = [
    'yf_fetch_all_stocks', 'fm_fetch_all_stocks',
    'send_line_message', 'send_email_with_csv',
    'upload_to_nas',
    'parse_stock_ids', 'get_stock_name_dict', 'send_report', 'cleanup_local_file', 'archive_and_cleanup'
]
