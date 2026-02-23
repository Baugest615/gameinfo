"""
情緒分析模組 — 基於 SnowNLP 的中文文本情緒判斷
score: 0.0 ~ 1.0 (0 = negative, 1 = positive)
label: "positive" | "neutral" | "negative"
"""
try:
    from snownlp import SnowNLP
    _HAS_SNOWNLP = True
except ImportError:
    _HAS_SNOWNLP = False
    print("[Sentiment] snownlp not available, sentiment analysis disabled")

POS_THRESHOLD = 0.6
NEG_THRESHOLD = 0.4


def analyze(text: str) -> dict:
    """分析單段中文文字的情緒"""
    if not _HAS_SNOWNLP or not text or not text.strip():
        return {"score": 0.5, "label": "neutral"}
    try:
        s = SnowNLP(text)
        score = round(s.sentiments, 3)
        if score >= POS_THRESHOLD:
            label = "positive"
        elif score <= NEG_THRESHOLD:
            label = "negative"
        else:
            label = "neutral"
        return {"score": score, "label": label}
    except Exception:
        return {"score": 0.5, "label": "neutral"}


def aggregate_sentiment(items: list[dict]) -> dict:
    """計算一批項目的整體情緒摘要（每項需有 sentiment key）"""
    if not items:
        return {"avg_score": 0.5, "label": "neutral",
                "positive_pct": 0, "negative_pct": 0, "neutral_pct": 100}

    scores = [it["sentiment"]["score"] for it in items if "sentiment" in it]
    if not scores:
        return {"avg_score": 0.5, "label": "neutral",
                "positive_pct": 0, "negative_pct": 0, "neutral_pct": 100}

    avg = sum(scores) / len(scores)
    labels = [it["sentiment"]["label"] for it in items if "sentiment" in it]
    total = len(labels)
    pos_pct = round(labels.count("positive") / total * 100, 1)
    neg_pct = round(labels.count("negative") / total * 100, 1)
    neu_pct = round(100 - pos_pct - neg_pct, 1)

    if avg >= POS_THRESHOLD:
        overall = "positive"
    elif avg <= NEG_THRESHOLD:
        overall = "negative"
    else:
        overall = "neutral"

    return {"avg_score": round(avg, 3), "label": overall,
            "positive_pct": pos_pct, "negative_pct": neg_pct, "neutral_pct": neu_pct}
