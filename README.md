# 建设性评论：Chrome 扩展 + 本地/云端 API（方案 A）

## 架构

1. **扩展**：在 YouTube 页面注入 `content.js`，从 DOM 读取评论文本 → 通过 **`background.js`（service worker）** `POST` 到本地/云端 API（避免 https 页面直连 `http://127.0.0.1` 的混合内容限制）→ 根据返回的 `scores` 筛选或排序。
2. **API**：FastAPI + `transformers`，加载你训练好的 `AutoModelForSequenceClassification`（与训练时同一 `tokenizer`）。

## 本地开发步骤

### 1. 准备模型（发给别人测试前做一次）

将 HuggingFace 导出的 **`best`** 目录复制到包内（**相对路径，与仓库位置无关**）：

```
constructive_extension/models/best/
```

详见 `models/README.md`。也可用环境变量覆盖：`CONSTRUCTIVE_MODEL_DIR`（相对路径相对于 `server/`）。

### 2. 启动 API

```bash
cd server
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8765
```

浏览器访问 http://127.0.0.1:8765/health 应返回 `ok: true` 及 `model_dir`。

浏览器扩展访问 `http://127.0.0.1:8765` 需在 `manifest.json` 的 `host_permissions` 里声明（已写）。

### 3. 安装扩展

1. 打开 Chrome → `chrome://extensions` → **开发者模式** → **加载已解压的扩展程序**  
2. 选择本目录下的 **`extension`** 文件夹。

### 4. 使用

1. 打开任意 YouTube 视频或 Shorts，**展开评论区**。  
2. 点击扩展图标（若配置了 popup）或等待几秒后页面出现 **「建设性：筛选 / 排序 / 恢复」** 按钮（由 `content.js` 注入）。  
3. **注意**：YouTube 前端 class 会变更，若按钮不出现或抓不到评论，需在 `content.js` 里更新选择器。

### 5. 打包给别人测试

整包发送 **`constructive_extension/`** 即可（建议内含 `models/best/`，体积较大可单独网盘说明「解压到 models/best」）。对方步骤：装依赖 → `uvicorn` → 加载 `extension`。无需改绝对路径。

### 6. 部署到论文演示

- 把 API 部署到 **HTTPS** 的小 VPS / Cloud Run；在 **`extension/background.js`** 里把 `API_BASE` 改为该 URL，并在 **`extension/manifest.json`** 的 `host_permissions` 中加入该域名（可保留或删除 localhost，视是否仍需本地调试而定）。  
- 生产环境建议加 **API Key**（`Authorization` 头）与 **速率限制**。

## YouTube DOM 说明

评论通常在 `ytd-comment-thread-renderer` 下，正文多为 `#content-text`。Shorts 可能结构略有不同，需 F12 实机确认后改 `SELECTORS`。

## 安全与条款

仅处理用户当前页面已加载的评论；请遵守 YouTube 服务条款，论文中注明为研究演示用途。
