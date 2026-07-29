# 網站內容管理說明

這一版不需要在電腦上執行程式，也不需要使用 Terminal、Git、GitHub Desktop 或 Personal Access Token。

## 第一次安裝後只要設定一次

1. 把這個資料夾的全部內容上傳到 `hctsui/hctsui.github.io` repository。
2. 到 GitHub repository 的 **Settings → General → Features**，確認 **Issues** 已開啟。
3. 到 **Settings → Actions → General → Workflow permissions**，選擇 **Read and write permissions**，再按 Save。
4. 確認 `.github` 資料夾也有上傳；它在 macOS Finder 中可能是隱藏資料夾。

## 平常新增資料

開啟：

> https://hctsui.github.io/admin/

選擇：

- 新增會議／工作坊
- 新增學術報告
- 新增學術訪問
- 新增獎項／榮譽
- 新增論文／預印本
- 新增教學課程

填完後按 **Submit new issue**。GitHub Actions 完成後，該 Issue 會自動留下完成訊息並關閉；中英文網頁會同步更新。

## Upcoming 的規則

Conference、Talk、Academic visit 的表單都有：

> Show on Upcoming? / 是否先顯示於 Upcoming

選擇 **Yes / 是** 時：

1. 活動結束以前，只顯示在首頁 Upcoming。
2. 每天的自動流程會檢查結束日期。
3. 結束日期過後，自動從 Upcoming 移除。
4. 同一筆資料自動加入 Activities 的對應區域：
   - Conference → Conferences and Workshops
   - Talk → Presentations
   - Academic visit → Academic visit
5. 英文版、中文版、排序與 Last updated 日期同步更新。

選擇 **No / 否** 時，資料會直接放入對應的正式列表。

## 編輯或刪除

1. 在 `/admin/` 下方搜尋項目。
2. 按「複製」取得 Entry ID。
3. 選「編輯既有項目」或「刪除既有項目」。
4. 貼上 Entry ID 並送出。

也可以在 repository 裡查看 `CONTENT-CATALOG.md`。

## 日期格式

日期一律填：

```text
YYYY-MM-DD
```

例如：

```text
2026-08-24
```

## 題目的斜體

一般情況直接輸入文字即可。論文或演講題目需要斜體時，可以使用：

```text
[i]u[/i]-Multiple Zeta Values
```

網站會顯示成斜體的 *u*。除此之外的 HTML 不會被接受，以避免破壞版面。

## 哪些檔案控制內容

- `content/site.json`：唯一的內容資料庫
- `tools/build_site.py`：按照既有 HTML 結構輸出內容
- `.github/ISSUE_TEMPLATE/`：你在 GitHub 看到的填表頁
- `.github/workflows/`：處理表單及 Upcoming 過期的自動流程

HTML 中只有 `<!-- CMS:... -->` 標記之間會由程式更新。其他文字、導覽列、版面、CSS、照片與 JavaScript 都不會被程式碰到。
