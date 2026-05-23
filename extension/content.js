/**
 * YouTube 评论：抓取 → API 打分 → 筛选 / 按建设性排序
 * YouTube 改版时需调整 SELECTORS。
 */
const MIN_LEN = 1;

// 常见结构（2024–2025 前后）；不可用请在 DevTools 里对着评论节点更新
const SELECTORS = {
  thread: "ytd-comment-thread-renderer",
  text: "#content-text, yt-formatted-string#content-text",
};

function getCommentThreads() {
  return Array.from(document.querySelectorAll(SELECTORS.thread));
}

function getTextFromThread(thread) {
  const el = thread.querySelector(SELECTORS.text);
  if (!el) return "";
  return el.innerText.replace(/\s+/g, " ").trim();
}

function scoreBatch(texts) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: "SCORE", texts }, (resp) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!resp || !resp.ok) {
        reject(new Error((resp && resp.error) || "スコア取得に失敗しました"));
        return;
      }
      resolve(resp.data);
    });
  });
}

function ensurePanel() {
  let p = document.getElementById("constructive-al-panel");
  if (p) return p;
  p = document.createElement("div");
  p.id = "constructive-al-panel";
  p.innerHTML = `
    <div><strong>建設的コメント（デモ）</strong></div>
    <button type="button" id="constructive-btn-score">スコア再計算・並べ替え</button>
    <button type="button" id="constructive-btn-filter" class="secondary">p≥0.5 のみ表示</button>
    <button type="button" id="constructive-btn-reset" class="secondary">元の表示に戻す</button>
    <div class="status" id="constructive-status">API: 127.0.0.1:8765（バックグラウンド経由）</div>
  `;
  document.body.appendChild(p);
  return p;
}

function setStatus(msg) {
  const s = document.getElementById("constructive-status");
  if (s) s.textContent = msg;
}

/** 最近一次为排序而改过 flex / order 的评论列表父节点（用于恢复） */
let lastReorderedParent = null;

/**
 * 按 scores 降序调整显示顺序。
 * 勿用 appendChild 移动 ytd-comment-thread-renderer：会打断 YouTube 自定义元素生命周期，导致骨架屏/无限加载。
 * 在父容器上使用 column flex，仅用 style.order 排序（分高者 order 更小，排在更前）。
 */
function reorderThreads(threads, scores) {
  if (threads.length === 0) return;
  const parent = threads[0].parentElement;
  if (!parent) return;
  lastReorderedParent = parent;

  const paired = threads.map((t, i) => ({ t, s: scores[i] }));
  paired.sort((a, b) => b.s - a.s);

  const cs = getComputedStyle(parent);
  const alreadyFlex = cs.display === "flex" || cs.display === "inline-flex";
  if (!alreadyFlex) {
    if (parent.dataset.constructiveSavedDisplay === undefined) {
      parent.dataset.constructiveSavedDisplay = parent.style.display || "";
      parent.dataset.constructiveSavedFlexDir = parent.style.flexDirection || "";
    }
    parent.style.display = "flex";
    parent.style.flexDirection = "column";
    parent.dataset.constructiveAppliedFlex = "1";
  }

  const ORDER_BASE = -1_000_000;
  paired.forEach(({ t }, rank) => {
    t.style.order = String(ORDER_BASE + rank);
  });
}

function restoreNativeCommentOrder() {
  document.querySelectorAll(SELECTORS.thread).forEach((t) => {
    t.style.order = "";
  });
  if (
    lastReorderedParent &&
    lastReorderedParent.dataset.constructiveAppliedFlex === "1"
  ) {
    lastReorderedParent.style.display =
      lastReorderedParent.dataset.constructiveSavedDisplay ?? "";
    lastReorderedParent.style.flexDirection =
      lastReorderedParent.dataset.constructiveSavedFlexDir ?? "";
    delete lastReorderedParent.dataset.constructiveAppliedFlex;
    delete lastReorderedParent.dataset.constructiveSavedDisplay;
    delete lastReorderedParent.dataset.constructiveSavedFlexDir;
  }
  lastReorderedParent = null;
}

function filterThreads(threads, scores, threshold) {
  threads.forEach((t, i) => {
    t.style.display = scores[i] >= threshold ? "" : "none";
  });
}

function showAllThreads(threads) {
  threads.forEach((t) => {
    t.style.display = "";
  });
}

let lastThreads = [];
let lastScores = [];

async function runScoreAndSort() {
  const threads = getCommentThreads().filter((t) => getTextFromThread(t).length >= MIN_LEN);
  if (threads.length === 0) {
    setStatus("コメントが見つかりません。コメント欄を開くか、SELECTORS を確認してください。");
    return;
  }
  const texts = threads.map(getTextFromThread);
  setStatus(`API に送信中…（${texts.length} 件）`);
  try {
    const data = await scoreBatch(texts);
    const scores = data.scores;
    if (!scores || scores.length !== threads.length) throw new Error("スコア件数が一致しません");
    lastThreads = threads;
    lastScores = scores;
    reorderThreads(threads, scores);
    setStatus(`完了。p の高い順に並べ替えました（${threads.length} 件）`);
  } catch (e) {
    setStatus(`エラー: ${e.message}（API は起動していますか？）`);
  }
}

function runFilter() {
  if (lastThreads.length === 0) {
    setStatus("先に「スコア再計算・並べ替え」を実行してください");
    return;
  }
  filterThreads(lastThreads, lastScores, 0.5);
  setStatus("p＜0.5 を非表示にしました（並べ替えで再取得できます）");
}

function runReset() {
  showAllThreads(getCommentThreads());
  restoreNativeCommentOrder();
  setStatus("表示とレイアウトを元に戻しました");
}

function init() {
  const panel = ensurePanel();
  panel.querySelector("#constructive-btn-score").addEventListener("click", runScoreAndSort);
  panel.querySelector("#constructive-btn-filter").addEventListener("click", runFilter);
  panel.querySelector("#constructive-btn-reset").addEventListener("click", runReset);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
