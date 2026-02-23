"""
遊戲討論情緒分析模組 — 基於 PTT 推噓比 + 遊戲領域關鍵字
不依賴外部 NLP 套件，純規則判斷
"""

# 遊戲領域正面/負面關鍵字
_POS_KEYWORDS = {
    "推薦", "好玩", "神作", "好評", "回歸", "首抽", "回鍋",
    "佛心", "良心", "必玩", "心得", "分享", "攻略", "教學",
    "恭喜", "太強", "好用", "開服", "週年", "慶祝", "免費",
    "更新", "優化", "感動", "期待", "入坑",
}

_NEG_KEYWORDS = {
    "雷", "爛", "糞作", "糞", "退坑", "炎上", "崩壞", "抵制",
    "倒閉", "關服", "停服", "詐騙", "課金", "坑錢", "劣化",
    "延期", "跳票", "過譽", "失望", "棄坑", "暴死", "翻車",
    "抄襲", "外掛", "掛機", "鎖區", "刪號",
}


def analyze_title(title: str) -> dict:
    """
    用遊戲關鍵字分析標題情緒
    回傳 {"label": "positive"|"negative"|"neutral"}
    """
    if not title:
        return {"label": "neutral"}

    pos_hits = sum(1 for kw in _POS_KEYWORDS if kw in title)
    neg_hits = sum(1 for kw in _NEG_KEYWORDS if kw in title)

    if pos_hits > neg_hits:
        return {"label": "positive"}
    elif neg_hits > pos_hits:
        return {"label": "negative"}
    return {"label": "neutral"}


def analyze_ptt_article(title: str, popularity_value: int) -> dict:
    """
    PTT 文章：結合推噓比 + 關鍵字判斷
    popularity_value: 100 = 爆, 正數 = 推多, 負數(X) = 噓多, 0 = 無
    回傳 {"label": "positive"|"negative"|"neutral"}
    """
    # 先看推噓比（權重較高，因為是真實用戶行為）
    if popularity_value >= 50:
        pop_signal = "positive"
    elif popularity_value < 0:
        pop_signal = "negative"
    else:
        pop_signal = "neutral"

    # 再看關鍵字
    kw = analyze_title(title)

    # 推噓比 > 關鍵字（真實行為優先）
    if pop_signal != "neutral":
        return {"label": pop_signal}
    return kw


def aggregate_sentiment(items: list[dict]) -> dict:
    """計算一批項目的整體情緒（每項需有 sentiment.label）"""
    if not items:
        return {"label": "neutral", "positive_pct": 0, "negative_pct": 0, "neutral_pct": 100}

    labels = [it["sentiment"]["label"] for it in items if "sentiment" in it]
    total = len(labels)
    if total == 0:
        return {"label": "neutral", "positive_pct": 0, "negative_pct": 0, "neutral_pct": 100}

    pos_pct = round(labels.count("positive") / total * 100, 1)
    neg_pct = round(labels.count("negative") / total * 100, 1)
    neu_pct = round(100 - pos_pct - neg_pct, 1)

    if pos_pct > neg_pct + 10:
        overall = "positive"
    elif neg_pct > pos_pct + 10:
        overall = "negative"
    else:
        overall = "neutral"

    return {"label": overall, "positive_pct": pos_pct, "negative_pct": neg_pct, "neutral_pct": neu_pct}
