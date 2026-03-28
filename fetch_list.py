import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

def fetch_histock_list(category_id, name_label):
    """
    抓取 HiStock 指定 ID 的成分股
    """
    url = f"https://histock.tw/global/globalclass.aspx?mid=0&id={category_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print(f"正在抓取 {name_label} 成分股 (ID={category_id})...")
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"無法連線至 {name_label}，狀態碼：{response.status_code}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'class': 'gvStandard'})
        
        if not table:
            print(f"在 {name_label} 頁面找不到資料表格")
            return pd.DataFrame()

        stock_data = []
        for row in table.find_all('tr')[1:]:
            cols = row.find_all('td')
            if len(cols) >= 2:
                # 取得代號與名稱
                code = cols[0].text.strip()
                name = cols[1].text.strip()
                # 只保留純數字的代號 (過濾掉可能出現的標題或其他文字)
                if code.isdigit():
                    stock_data.append({'code': code, 'name': name})

        return pd.DataFrame(stock_data)

    except Exception as e:
        print(f"抓取 {name_label} 時出錯: {e}")
        return pd.DataFrame()

def main():
    # 1. 分別抓取台灣 50 (ID=2) 與 中型 100 (ID=3)
    df_tw50 = fetch_histock_list(2, "台灣 50")
    time.sleep(2) # 延遲 2 秒，避免請求過快
    df_mid100 = fetch_histock_list(3, "中型 100")
    
    # 2. 合併資料
    full_list = pd.concat([df_tw50, df_mid100], ignore_index=True)
    
    # 3. 去除重複項 (若有股票同時屬於兩個指數)
    full_list = full_list.drop_duplicates(subset=['code'])
    
    if not full_list.empty:
        # 4. 排序並儲存
        full_list = full_list.sort_values(by='code')
        full_list.to_csv('stock_list.csv', index=False, encoding='utf-8-sig')
        print(f"--- 任務完成 ---")
        print(f"總共取得 {len(full_list)} 檔不重複個股，已存入 stock_list.csv")
    else:
        print("警告：未抓取到任何資料，請檢查網路或網頁結構。")

if __name__ == "__main__":
    main()
