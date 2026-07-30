# 網站與雙語 CV 管理說明

日常入口：

> https://hctsui.github.io/admin/

## 新增、編輯、刪除與排序

Admin 可新增 Conference、Talk、Visit、Honor、Publication、Teaching，也可搜尋、編輯、刪除及持久化排序。

- Publication 依作品類型分組；PDF CV 在每個大標題內重新從 `[1]` 編號。
- Teaching 依機構分組。
- 自訂群組會加入後續表單；刪除最後一筆後，空的自訂群組會自動移除。
- Conference、Talk、Visit、Honor、Publication、Teaching 六類皆可排序。

## 雙語欄位補全

每張含雙語欄位的表單都有：

- `Keep blanks / 空白保持空白`：預設。沒有填的另一種語言保持空白。
- `Use Admin dictionary / 使用 Admin 中英對照表補全`：只查 `content/translations.json` 的完整一對一對照。

補全規則：

- 英文有值、中文空白：英文在對照表完全命中時才填中文。
- 中文有值、英文空白：中文在對照表完全命中時才填英文。
- 找不到：保持空白。
- 不使用 AI、模糊比對、同系列活動名稱、舊網站內容或其他推測。

新增資料時，主要題目或名稱只要求至少一種語言。編輯既有資料時，空白欄位代表「維持原值」；要清除某個既有語言欄位，請輸入 `[CLEAR]`。

## 編輯中英對照資料庫

在 Admin 的「中英對照資料庫」中：

1. 可直接新增、修改、刪除及搜尋對照。
2. 修改會立即保存在目前瀏覽器的本機草稿，不會每列送一次 Issue。
3. 對照表修改會與其他內容草稿一起出現在右側預覽。
4. 按「前往 GitHub 送出批次」後建立一張 Issue；大型批次會自動 gzip 壓縮，貼入單欄表單即可；後端會自動解壓，不會碰到 GitHub 單一欄位 65,536 字元限制。
5. GitHub Action 成功寫入後，Issue 會出現 `website-form-applied` 標籤與完成訊息，並由同一個 workflow 的後續 deployment job 建立網站與 PDF。確認完成後，再回 Admin 手動清除本機草稿。

若遠端對照表在本機草稿期間已更新，Admin 不會自動套用舊草稿，以避免覆蓋他人的新資料。

程式會拒絕：

- 任一側空白的資料列。
- 完全重複的對照列（包含 Unicode NFKC 正規化後的重複）。
- 同一英文對應多個中文。
- 同一中文對應多個英文。

## 英文與中文 PDF CV

同一份 `content/site.json` 會產生：

- 英文 CV：`https://hctsui.github.io/files/Hung-Chun-Tsui-CV.pdf`
- 中文 CV：`https://hctsui.github.io/files/Hung-Chun-Tsui-CV-zh.pdf`

英文 CV 頁面下載英文版，中文 CV 頁面下載中文版。中文 CV 使用 XeLaTeX、ctex 與 Noto CJK 繁體中文字型編譯。

## Upcoming

Conference、Talk、Visit 可選擇先顯示在 Upcoming。結束日期過後，每日 workflow 會重新生成網站與兩份 CV。

## 日期與斜體

日期使用 `YYYY-MM-DD`。題目中需要斜體時可寫：

```text
[i]u[/i]-Multiple Zeta Values
```

## 主要檔案

- `content/site.json`：網站與 CV 的內容資料庫
- `content/translations.json`：唯一的中英對照資料庫
- `tools/process_request.py`：單筆表單處理及精確補全
- `tools/process_batch_request.py`：Admin 批次交易、衝突檢查與七日還原
- `tools/translation_validation.py`：單筆、批次與最終驗證共用的對照表規則
- `tools/build_site.py`：網站生成
- `tools/build_cv.py`：英文及中文 LaTeX CV 生成
- `cv/Hung-Chun-Tsui-CV.template.tex`：英文 CV 模板
- `cv/Hung-Chun-Tsui-CV-zh.template.tex`：中文 CV 模板


## 學術訪問 Funding

Admin 的學術訪問表單可另外填寫 Funding（機構或計畫）。儲存時會自動將英文整理為 `Supported by …`，中文整理為「本次訪問獲……支持。」並附加到說明中。
