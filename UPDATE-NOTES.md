# Admin 修正更新包

基底版本：`cms` commit `84eac784d5d91b1f4386457364bda159a96a1b8f`（2026-07-31）。

將本壓縮檔內容解壓到 repository 根目錄並覆蓋同名檔案：

- `admin/homepage-v1.js`
- `admin/guide.html`
- `MANAGE-WEBSITE.md`

## 修正內容

1. 首頁精選併入「排序」後，改用局部更新與明確草稿狀態，避免被排序頁重繪干擾。
2. 「項目」的搜尋、項目類型篩選與檢視排序，統一呼叫新版標籤渲染，不再退回舊標籤。
3. 一般內容新增與編輯都可選六種顯示風格，表單內附即時版面縮圖。
4. 每個排序項目都顯示「搬移」選單；沒有相容類別時保持顯示但停用。
5. 跨越「精簡時間軸（榮譽）」與其他一般內容格式時，以安全的刪除＋新增草稿處理，同一批次送出。
6. 更新 Admin HTML 手冊與 repository 管理說明。
7. 補回既有測試要求的完整手冊章節：標準工作流程、欄位與自動填寫、排序／頁面／類別、送出前檢查及還原。

## 已執行檢查

- `node --check admin/homepage-v1.js`
- Node VM smoke test：新版搜尋／篩選事件綁定、停用搬移選單輸出。
- 更新包靜態回歸測試：`tests/test_admin_hotfix.py`（5 項通過）
- `tests/test_cms.py` 的手冊固定章節字串檢查：通過

GitHub connector 在本次工作中可讀取 repository，但建立分支、更新 ref 與寫入檔案均回傳權限／安全層拒絕，因此此包尚未由助理推送至 GitHub。
