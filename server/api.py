"""
建设性评论打分 API（本地/服务器）
启动: uvicorn api:app --host 0.0.0.0 --port 8765
"""
import json
import os
import shutil
import tempfile
from typing import List

import numpy as np
import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# 默认：与本包捆绑的相对路径 constructive_extension/models/best（便于整包发给别人测试）
# 也可通过环境变量 CONSTRUCTIVE_MODEL_DIR 覆盖（可为相对或绝对路径）
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.dirname(_SERVER_DIR)
_DEFAULT_MODEL = os.path.join(_PKG_ROOT, "models", "best")


def _resolve_model_dir(raw: str) -> str:
    p = os.path.expanduser(raw.strip())
    if not os.path.isabs(p):
        p = os.path.normpath(os.path.join(_SERVER_DIR, p))
    return os.path.abspath(p)


_MODEL_DIR_RAW = os.environ.get("CONSTRUCTIVE_MODEL_DIR", _DEFAULT_MODEL)
MODEL_DIR = _resolve_model_dir(_MODEL_DIR_RAW)

MAX_LEN = 512
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI(title="Constructive Score API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_tokenizer = None
_model = None


def _sanitize_tokenizer_config_dict(tc: dict) -> dict:
    """去掉无效的 tokenizer_class / auto_map（部分环境 save_pretrained 会写入 TokenizersBackend，非有效 Python 类名）。"""
    out = dict(tc)
    out.pop("tokenizer_class", None)
    out.pop("fast_tokenizer_class", None)
    am = out.get("auto_map")
    if isinstance(am, dict):
        cleaned = {k: v for k, v in am.items() if "TokenizersBackend" not in str(v)}
        if cleaned:
            out["auto_map"] = cleaned
        else:
            out.pop("auto_map", None)
    elif am is not None and "TokenizersBackend" in str(am):
        out.pop("auto_map", None)
    return out


def _copy_tokenizer_sidecars(src_dir: str, dst_dir: str) -> None:
    """复制 config.json、词表等小文件；不复制 .safetensors / 大体积 .bin 权重。
    transformers>=4.40 在加载 AutoTokenizer 时会先读 config.json 的 model_type，临时目录必须带该文件。"""
    for name in os.listdir(src_dir):
        sp = os.path.join(src_dir, name)
        if not os.path.isfile(sp):
            continue
        low = name.lower()
        sz = os.path.getsize(sp)
        if low.endswith(".safetensors"):
            continue
        if low.endswith(".bin") and sz > 2 * 1024 * 1024 and "token" not in low:
            continue
        if sz > 200 * 1024 * 1024:
            continue
        shutil.copy2(sp, os.path.join(dst_dir, name))


def _load_tokenizer_from_sanitized_staging_dir(model_dir: str):
    """导出目录里 tokenizer_config.json 含非法类名时，在临时目录写入修正后的配置再加载（不改你磁盘上的原文件）。"""
    tc_path = os.path.join(model_dir, "tokenizer_config.json")
    if not os.path.isfile(tc_path):
        raise ValueError(f"缺少 tokenizer_config.json: {model_dir}")
    cfg_path = os.path.join(model_dir, "config.json")
    if not os.path.isfile(cfg_path):
        raise ValueError(
            f"缺少 config.json（内含 model_type），AutoTokenizer 无法推断词表类型: {model_dir}"
        )
    with open(tc_path, encoding="utf-8") as f:
        tc = _sanitize_tokenizer_config_dict(json.load(f))
    tmp = tempfile.mkdtemp(prefix="constructive_tok_")
    _copy_tokenizer_sidecars(model_dir, tmp)
    with open(os.path.join(tmp, "tokenizer_config.json"), "w", encoding="utf-8") as f:
        json.dump(tc, f, indent=2, ensure_ascii=False)
    last_err = None
    for use_fast in (True, False):
        try:
            return AutoTokenizer.from_pretrained(tmp, use_fast=use_fast, local_files_only=True)
        except (ValueError, OSError) as e:
            last_err = e
    shutil.rmtree(tmp, ignore_errors=True)
    raise last_err  # type: ignore[misc]


def _load_tokenizer(model_dir: str):
    """与训练时一致：AutoTokenizer.from_pretrained(导出目录)。仅当 tokenizer_config 含非法类名时再走 staging。"""
    last_err = None
    for use_fast in (True, False):
        try:
            return AutoTokenizer.from_pretrained(model_dir, use_fast=use_fast)
        except (ValueError, OSError) as e:
            last_err = e
    err_txt = str(last_err) if last_err else ""
    if "TokenizersBackend" in err_txt or "does not exist or is not currently imported" in err_txt:
        return _load_tokenizer_from_sanitized_staging_dir(model_dir)
    raise last_err  # type: ignore[misc]


def get_model():
    global _tokenizer, _model
    if _model is None:
        if not os.path.isdir(MODEL_DIR):
            raise RuntimeError(
                f"模型目录不存在: {MODEL_DIR}\n"
                "请将训练导出的 HuggingFace 目录（含 config.json、tokenizer*、model.safetensors 等）"
                f"复制到包内默认位置: {_DEFAULT_MODEL}\n"
                "或通过环境变量指定（相对路径相对于 server/ 目录）:\n"
                "  PowerShell: $env:CONSTRUCTIVE_MODEL_DIR='..\\models\\best'\n"
                "  bash: export CONSTRUCTIVE_MODEL_DIR=../models/best"
            )
        _tokenizer = _load_tokenizer(MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_DIR, num_labels=2
        )
        _model.eval()
        _model.to(DEVICE)
    return _tokenizer, _model


def logits_to_p1(logits: torch.Tensor) -> np.ndarray:
    logits = logits.float()
    logits = logits - logits.max(dim=-1, keepdim=True).values
    pr = torch.exp(logits)
    pr = pr / pr.sum(dim=-1, keepdim=True)
    return pr[:, 1].detach().cpu().numpy()


class ScoreRequest(BaseModel):
    texts: List[str]


class ScoreResponse(BaseModel):
    scores: List[float]


@app.get("/health")
def health():
    return {"ok": True, "model_dir": MODEL_DIR, "device": DEVICE}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    texts = [t.replace("\n", " ").strip() for t in req.texts]
    tok, model = get_model()
    scores_out: List[float] = []
    batch = 16
    with torch.inference_mode():
        for i in range(0, len(texts), batch):
            chunk = texts[i : i + batch]
            enc = tok(
                chunk,
                truncation=True,
                max_length=MAX_LEN,
                padding=True,
                return_tensors="pt",
            )
            enc = {k: v.to(DEVICE) for k, v in enc.items()}
            logits = model(**enc).logits
            p1 = logits_to_p1(logits)
            scores_out.extend(float(x) for x in p1)
    return ScoreResponse(scores=scores_out)
