# 配電盤線材紀錄表 · 展示版

以 Streamlit 開發的繁體中文線材製作表，供公開展示與試填。

- Excel 式左右端加工對照表，支援多芯、雙絞、64 色色卡與軍規／動力接頭。
- 線材／浪管長度使用 cm，剝皮使用 mm。
- 每個訪客使用獨立連線記憶體，只載入內建示範資料。
- 不會讀寫正式資料庫，不開放檔案匯入；請勿輸入正式工程或個人資料。
- 可儲存目前連線中的試填內容、下載示範資料，或按「重設展示資料」。重新整理或斷線後資料可能重設。

## 執行

```sh
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Streamlit Community Cloud：使用 main 分支、streamlit_app.py 入口。此專案只包含展示程式及內建示例，不含原始工程 Excel、資料庫或私人專案紀錄。
