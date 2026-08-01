# 聯絡表單設定：一步一步完成

網站提供兩種模式：

1. **Web3Forms Email**：設定最簡單，訊息只寄到 Email，不在 Admin 建立通知。
2. **Cloudflare Worker 橋接**：訊息寄到 Email，並在 Admin 建立一則不含個資的匿名通知。

建議先完成第一種，確認收信正常後，再決定是否升級到 Worker 模式。

---

## A. 最簡單：只寄到 Email

### 步驟 1：建立 Web3Forms Access Key

1. 開啟 Web3Forms 官網。
2. 輸入要收信的 Email。
3. 按照 Web3Forms 寄來的驗證信完成驗證。
4. 複製產生的 **Access Key**。

Access Key 會放在公開網頁表單中；Web3Forms 的設計允許它出現在前端。不要把 Cloudflare Secret 或 GitHub Token 混在這裡。

### 步驟 2：填入 Admin

1. 開啟網站 Admin。
2. 點「網站設定」。
3. 點「聯絡表單」。
4. 勾選「啟用聯絡表單」。
5. 「傳送模式」選 **Web3Forms Email（免費、無 Admin 通知）**。
6. 在「Web3Forms Access Key」貼上剛才複製的 Key。
7. 在「通知信固定主旨」填入固定文字，例如：

   ```text
   [hctsui.github.io] New contact message
   ```

   每封通知信都會使用這個主旨，方便在 Gmail 建立篩選器。訪客填寫的主旨會出現在信件內容裡。
8. 視需要修改中英文標題與欄位名稱。
9. 到「草稿」確認出現「網站設定」管理列。
10. 預覽後，和其他草稿一起送出 Batch Issue。

### 步驟 3：測試

1. 等 GitHub Actions 部署成功。
2. 用無痕視窗開啟首頁。
3. 在聯絡區填入測試訊息。
4. 確認信箱收到固定主旨的信。
5. 在 Gmail 建立篩選器時，條件可使用：

   ```text
   subject:[hctsui.github.io] New contact message
   ```

這個模式不會在 Admin 產生通知，屬正常行為。

---

## B. 進階：Email 加上 Admin 匿名通知

這個模式需要 Cloudflare Worker。完整留言仍只寄到 Email；公開 repository 只會收到隨機事件 ID 和時間。

### 步驟 1：準備 Web3Forms Access Key

沿用 A 模式建立的 Access Key。

### 步驟 2：建立 GitHub fine-grained token

1. 到 GitHub Settings。
2. 進入 Developer settings → Personal access tokens → Fine-grained tokens。
3. 建立新 token。
4. Repository access 選 **Only select repositories**。
5. 只選 `hctsui/hctsui.github.io`。
6. Repository permissions 將 **Contents** 設為 **Read and write**。
7. 產生 token，立刻複製保存；GitHub 之後不會完整顯示第二次。

這個 token 只交給 Cloudflare Worker Secret，不得貼進 Admin、程式碼或 repository。

### 步驟 3：建立 Cloudflare Worker

1. 登入 Cloudflare Dashboard。
2. 前往 **Workers & Pages**。
3. 建立一個 Worker，例如 `hctsui-contact`。
4. 開啟 Worker 編輯器。
5. 把 repository 內的 `integrations/contact-worker.js` 全部貼入。
6. Deploy。
7. 複製 Worker URL，例如：

   ```text
   https://hctsui-contact.<你的子網域>.workers.dev
   ```

### 步驟 4：加入 Worker Secrets

在 Worker 的 Settings／Variables and Secrets 中，加入下列 **Secrets**：

| 名稱 | 內容 |
|---|---|
| `WEB3FORMS_ACCESS_KEY` | Web3Forms Access Key |
| `GITHUB_TOKEN` | 上一步建立的 fine-grained token |
| `TURNSTILE_SECRET` | 下一步建立 Turnstile 後取得的 Secret Key |

Secret 的值不能放到普通變數，也不能提交到 GitHub。

### 步驟 5：建立 Turnstile

1. 在 Cloudflare Dashboard 開啟 Turnstile。
2. 建立新 Widget。
3. Hostname 加入 `hctsui.github.io`。
4. 建議使用 Managed 模式。
5. 建立後取得：
   - **Site Key**：公開，可填入 Admin。
   - **Secret Key**：私密，只填入 Worker Secret `TURNSTILE_SECRET`。

### 步驟 6：加入 Worker 普通變數

在同一個 Worker 設定下加入下列 **Variables**：

| 名稱 | 建議值 |
|---|---|
| `SITE_ORIGIN` | `https://hctsui.github.io` |
| `GITHUB_REPOSITORY` | `hctsui/hctsui.github.io` |
| `EMAIL_SUBJECT` | `[hctsui.github.io] New contact message` |

`EMAIL_SUBJECT` 建議和 Admin 的「通知信固定主旨」完全相同。

### 步驟 7：填入 Admin

1. 開啟「網站設定 → 聯絡表單」。
2. 勾選「啟用聯絡表單」。
3. 傳送模式選 **Cloudflare Worker 橋接（Email＋匿名 Admin 通知）**。
4. 「通知信固定主旨」填入和 Worker `EMAIL_SUBJECT` 相同的文字。
5. 「Cloudflare Worker URL」貼入 Worker URL。
6. 「Cloudflare Turnstile Site Key」貼入公開 Site Key。
7. 到主「草稿」分頁確認網站設定草稿。
8. 預覽並送出 Batch Issue。

### 步驟 8：完整測試

1. 等 GitHub Actions 部署成功。
2. 用無痕視窗開啟首頁。
3. 完成 Turnstile 並送出測試訊息。
4. 確認 Email 收到固定主旨的信。
5. 打開 Admin → 通知。
6. 應看到一則「收到新的網站聯絡訊息」匿名通知。
7. 通知右上角可按「☆ 加星號」。
8. 完成處理後可按「標記為已處理」。

---

## C. Admin 直接送出到 GitHub

這個功能沿用同一個 Cloudflare Worker。GitHub OAuth 只確認登入者是 repository owner；建立 Batch Issue 使用 Worker Secret 中的 fine-grained token。任何 GitHub Token 都不得放進 Admin 或公開 repository。

### 步驟 1：替 fine-grained token 加上 Issue 權限

`GITHUB_TOKEN` 需要 **Contents: Read and write** 與 **Issues: Read and write**。Token 必須由 `hctsui` 帳號建立，並且只允許 `hctsui/hctsui.github.io`。

### 步驟 2：建立 GitHub OAuth App

在 GitHub → Settings → Developer settings → OAuth Apps 建立一個 OAuth App：

| 欄位 | 值 |
|---|---|
| Application name | `hctsui CMS Submit` |
| Homepage URL | `https://hctsui.github.io/admin/` |
| Authorization callback URL | `https://hctsui-website-worker.hctsui-math.workers.dev/cms/auth/callback` |

建立後取得 Client ID，並產生一個 Client Secret。Client Secret 只能放進 Cloudflare Worker Secret。

### 步驟 3：加入 Worker Secrets 與 Variables

新增下列 **Secret**：

| 名稱 | 內容 |
|---|---|
| `GITHUB_OAUTH_CLIENT_SECRET` | OAuth App Client Secret |

目前網站的公開 OAuth Client ID 已寫入 Worker。`CMS_SESSION_SECRET` 可選填；未設定時 Worker 會從 OAuth Client Secret 衍生簽章金鑰，不會把 Secret 傳到瀏覽器。

新增下列普通 **Variables**：

| 名稱 | 值 |
|---|---|
| `ADMIN_URL` | `https://hctsui.github.io/admin/` |
| `CMS_ALLOWED_GITHUB_LOGIN` | `hctsui` |

### 步驟 4：更新並測試 Worker

部署 repository 中的 `integrations/contact-worker.js`。開啟 Admin，若尚未登入 GitHub，就先完成驗證，再按「直接送出修改」。確認修改請求建立成功，並測試「改用 GitHub Issue 手動送出」備用入口。

---

## D. Admin 流量報表（Cloudflare＋Google）

報表沿用上面的 GitHub 14 天登入。瀏覽器只收到彙整後的流量資料；API Token、服務帳戶私鑰都只放在 Worker Secret。

### Cloudflare Web Analytics

1. 在 Cloudflare 右上角個人選單開啟 **My Profile → API Tokens → Create Token → Custom token**。
2. 權限只選 **Account → Account Analytics → Read**；Account Resources 限定目前網站所在帳戶，不要加入寫入權限。
3. 建立後立刻複製 Token。離開頁面後 Cloudflare 不會再顯示完整 Token。
4. 回到 **Workers & Pages → hctsui-website-worker → Settings → Variables and Secrets**，新增下列設定：

| 類型 | 名稱 | 內容 |
|---|---|---|
| Secret | `CLOUDFLARE_ANALYTICS_API_TOKEN` | 只含 **Account → Account Analytics → Read** 的 API Token |
| Variable | `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID |
| Variable（選填） | `ANALYTICS_SITE_HOST` | `hctsui.github.io`；未填時會從 `SITE_ORIGIN` 自動取得 |

Account ID 可在 Worker 的設定頁或 Cloudflare Dashboard 網址中找到。公開頁面的 32 字元 Site Token 只負責送出追蹤資料，不是報表讀取憑證。報表會用網域篩選 Cloudflare Web Analytics 資料。儲存後部署 Worker，再回 Admin 的流量統計按「重新檢查」。

### Google Analytics 4

1. 在 Google Cloud 啟用 **Google Analytics Data API**，建立服務帳戶並下載 JSON 金鑰。
2. 在 GA4 Property → 存取權管理，把 JSON 內的 `client_email` 加成 **檢視者（Viewer）**。
3. 新增下列 Worker 設定：

| 類型 | 名稱 | 內容 |
|---|---|---|
| Secret | `GOOGLE_ANALYTICS_SERVICE_ACCOUNT_JSON` | 完整的服務帳戶 JSON |
| Variable | `GOOGLE_ANALYTICS_PROPERTY_ID` | 純數字 GA4 Property ID；不是 `G-...` Measurement ID |

完成後重新部署 Worker，開啟 Admin → 網站設定 → 流量統計，選擇提供者即可查看今天、7 天、30 天與 90 天報表。

---

## 常見問題

### Email 有收到，但 Admin 沒通知

依序檢查：

1. Admin 是否選 Worker 模式。
2. Worker 是否設定 `GITHUB_TOKEN`。
3. Token 是否只授權正確 repository，且 Contents 為 Read and write。
4. Worker Log 是否顯示 GitHub API 錯誤。
5. `.github/workflows/ingest-contact.yml` 是否已上傳。

Email 是主要操作；即使 GitHub 通知建立失敗，Worker 仍可能回報寄信成功。

### Turnstile 一直失敗

確認：

- Widget hostname 是 `hctsui.github.io`。
- Admin 填的是 Site Key。
- Worker Secret 填的是 Secret Key。
- 兩者沒有填反。

### 信件主旨不是固定文字

- Email 模式：確認 Admin 的「通知信固定主旨」已送出並完成部署。
- Worker 模式：確認 Worker 變數 `EMAIL_SUBJECT` 和 Admin 設定相同，修改 Worker 變數後重新 Deploy。

### 安全原則

以下資料絕不可填進 Admin 或提交到 repository：

- `GITHUB_TOKEN`
- `TURNSTILE_SECRET`
- Worker 中的任何私密 Secret

公開頁面只包含 Web3Forms Access Key、Worker URL 與 Turnstile Site Key。


### Batch 顯示 Worker URL 缺失

若 GitHub Action 顯示 `Worker URL is missing or invalid`，代表聯絡表單已勾選啟用且傳送模式是 Cloudflare Worker，但尚未填入完整 Worker URL。請回到 Admin → 網站設定 → 聯絡表單，選擇其中一種處理方式：

1. 填入完整的 `https://...workers.dev` 網址；
2. 改選 Web3Forms Email 並填入 Access Key；
3. 尚未設定完成時，先取消「啟用聯絡表單」。

修正設定後建立新的 Batch Issue；失敗的 Issue 不會自動套用新內容。
