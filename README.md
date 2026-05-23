# 建設的コメント分類デモ（Chrome 拡張 + ローカル API）

研究用デモです。YouTube の**すでに画面に表示されているコメント**を読み取り、建設性スコア（確率 *p*）で並べ替え・フィルタできます。

**テスター向け**：下の「使い方」だけ順に進めてください。コードの改変は不要です。

---

## 必要なもの

| 項目 | 内容 |
|------|------|
| OS | Windows 10/11 または macOS（Linux も可） |
| ブラウザ | **Google Chrome** |
| Python | **3.9 以上** |
| モデル | 別途配布の ZIP（約 500MB）→ 後述の場所に展開 |
| ネット | YouTube 閲覧用 + `pip install` 用 |

---

## 1. リポジトリの取得

### GitHub から clone する場合

```bash
git clone https://github.com/Feng-ron/constructive-comment-demo.git
cd constructive-comment-demo
```

※ リポジトリ名は配布時の URL に合わせてください。フォルダ名が `constructive_extension_demo` の場合は、以降の `cd` をそれに読み替えてください。

### ZIP で受け取った場合

ZIP を解凍し、ターミナル（PowerShell など）で**そのフォルダの中**に入ってください。

```powershell
cd 解凍先\constructive_extension_demo
```

---

## 2. モデルファイルの配置（必須）

GitHub には**モデルは含まれていません**。配布者から受け取った ZIP（例：`model-best.zip`）を展開し、次の構成にしてください。

```
constructive_extension_demo/
  models/
    best/
      config.json
      model.safetensors
      tokenizer.json
      tokenizer_config.json
      ...
```

展開後、次のコマンドで中身があるか確認できます（任意）：

**Windows（PowerShell）**

```powershell
dir models\best
```

**macOS / Linux**

```bash
ls models/best
```

`model.safetensors` があることが重要です。

---

## 3. API サーバーの起動

### 3.1 依存パッケージのインストール

**Windows（PowerShell）**

```powershell
cd server
pip install -r requirements.txt
```

**macOS / Linux**

```bash
cd server
pip install -r requirements.txt
```

エラーが出た場合は `python -m pip install -r requirements.txt` を試してください。

### 3.2 サーバー起動

同じ `server` フォルダで：

```bash
uvicorn api:app --host 0.0.0.0 --port 8765
```

次のような表示が出れば起動成功です。

```
Uvicorn running on http://0.0.0.0:8765
```

**このウィンドウは閉じないでください**（閉じると拡張が動きません）。

### 3.3 動作確認

Chrome で次を開きます。

http://127.0.0.1:8765/health

`"ok": true` と `"model_dir"` が表示されれば OK です。

---

## 4. Chrome 拡張のインストール

1. Chrome のアドレスバーに `chrome://extensions` と入力して Enter  
2. 右上 **developer mode** をオン  
3. **パッケージ化されていない拡張機能を読み込む** をクリック  
4. リポジトリ内の **`extension`** フォルダを選択  
   - ⚠️ 親フォルダ全体ではなく、必ず **`extension`** だけを選んでください  
5. 一覧に **「建設的コメント（デモ）」** が表示されれば完了  

---

## 5. YouTube での使い方

1. 任意の **YouTube Shorts動画** を開く  
2. **コメント欄を開き**、コメントが表示されるまでスクロール（読み込まれた分だけが対象です）  
3. 画面右下付近に **「建設的コメント（デモ）」** パネルが表示されます  

| ボタン | 操作内容 |
|--------|----------|
| **スコア再計算・並べ替え** | 表示中のコメントを API に送り、建設性スコア *p* の**高い順**に並べ替え |
| **p≥0.5 のみ表示** | 上の操作の**後**に押す。スコア 0.5 未満のコメントを非表示 |
| **元の表示に戻す** | YouTube の元の順序・表示に戻す |

パネル下部のステータス行に進捗やエラー（日本語）が表示されます。

### うまくいかないとき

| 症状 | 対処 |
|------|------|
| `API は起動していますか？` | 手順 3 の `uvicorn` が動いているか確認 |
| `コメントが見つかりません` | コメント欄を開く／もっとスクロールして読み込む |
| `/health` でモデルエラー | 手順 2 の `models/best` を確認 |
| ボタンが出ない | ページを再読み込み（F5）、拡張が有効か `chrome://extensions` で確認 |

---

## 6. テスト後のフィードバック（ご協力お願いします）

Slack などで、次の点を共有いただけると助かります。

- OS（Windows / macOS など）と Python バージョン  
- `/health` は成功したか  
- 並べ替え・フィルタは期待どおりか（例・スクリーンショット歓迎）  
- エラーメッセージ（パネル下部の全文）  
- UI の分かりやすさ、研究デモとしての感想  

---

## フォルダ構成（参考）

```
constructive_extension_demo/
  extension/     … Chrome 拡張（読み込むのはこのフォルダ）
  server/        … ローカル API（api.py, requirements.txt）
  models/best/   … 学習済みモデル（各自で配置）
  README.md      … 本ファイル
```



---

## 注意事項

- 画面上に読み込まれたコメントのみを処理します（全 YouTube を収集しません）。
- **YouTube の利用規約**を守ってください。本ツールは**研究・デモ目的**です。
- YouTube の画面仕様変更により、コメントが取得できなくなる場合があります。その際は開発者に連絡してください。
