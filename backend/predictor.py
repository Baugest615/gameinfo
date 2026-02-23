"""
AI 熱度預測模組 — 加權線性回歸 + 日週期調整
純 Python 實作（statistics + math），不依賴 numpy
輸入：歷史資料點 [{"value": N, "recorded_at": unix_ts}, ...]
輸出：24 筆未來預測 [{"value": N, "recorded_at": ts, "is_forecast": true}, ...]
"""
import datetime
import math
import statistics
from collections import defaultdict


MIN_HOURS = 6  # 最少需 6 筆小時資料才產生預測
FORECAST_HOURS = 24


def _hourly_downsample(data: list[dict]) -> list[dict]:
    """將原始資料按小時取均值，回傳 [{"hour_ts": ts, "value": avg}, ...]"""
    buckets = defaultdict(list)
    for d in data:
        ts = d["recorded_at"]
        hour_ts = (ts // 3600) * 3600
        buckets[hour_ts].append(d["value"])

    result = []
    for hour_ts in sorted(buckets):
        avg_val = statistics.mean(buckets[hour_ts])
        result.append({"hour_ts": hour_ts, "value": avg_val})
    return result


def _weighted_linear_regression(points: list[dict]) -> tuple[float, float]:
    """加權線性回歸，近期資料權重更高。回傳 (slope, intercept)"""
    n = len(points)
    if n < 2:
        return 0.0, points[0]["value"] if points else 0.0

    # 權重：指數遞增，最新的點權重最大
    weights = [math.exp(i / n) for i in range(n)]
    total_w = sum(weights)

    # x 軸用小時索引（0, 1, 2, ...）
    xs = list(range(n))

    # 加權均值
    mean_x = sum(w * x for w, x in zip(weights, xs)) / total_w
    mean_y = sum(w * p["value"] for w, p in zip(weights, points)) / total_w

    # 加權協方差與方差
    num = sum(w * (x - mean_x) * (p["value"] - mean_y) for w, x, p in zip(weights, xs, points))
    den = sum(w * (x - mean_x) ** 2 for w, x in zip(weights, xs))

    if abs(den) < 1e-10:
        return 0.0, mean_y

    slope = num / den
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _daily_cycle_factors(hourly_data: list[dict]) -> dict[int, float]:
    """計算每小時相對均值的週期因子（0-23 小時）"""
    hour_groups = defaultdict(list)
    for d in hourly_data:
        hour = datetime.datetime.fromtimestamp(d["hour_ts"]).hour
        hour_groups[hour].append(d["value"])

    overall_mean = statistics.mean(d["value"] for d in hourly_data) if hourly_data else 1.0
    if overall_mean == 0:
        overall_mean = 1.0

    factors = {}
    for h in range(24):
        if h in hour_groups and len(hour_groups[h]) >= 1:
            factors[h] = statistics.mean(hour_groups[h]) / overall_mean
        else:
            factors[h] = 1.0

    return factors


def predict(data_points: list[dict]) -> list[dict]:
    """
    從歷史資料產生 24 小時預測
    data_points: [{"value": N, "recorded_at": unix_ts}, ...]
    回傳: [{"value": N, "recorded_at": ts, "is_forecast": true}, ...]
    """
    if not data_points:
        return []

    hourly = _hourly_downsample(data_points)

    if len(hourly) < MIN_HOURS:
        return []

    # 線性回歸
    slope, intercept = _weighted_linear_regression(hourly)

    # 日週期因子
    cycle = _daily_cycle_factors(hourly)

    # 產生預測：從最後一筆之後開始
    last_ts = hourly[-1]["hour_ts"]
    n = len(hourly)  # 回歸 x 軸的末端索引

    forecasts = []
    for i in range(1, FORECAST_HOURS + 1):
        future_ts = last_ts + i * 3600
        # 線性趨勢值
        trend_val = slope * (n + i) + intercept
        # 套用日週期因子
        hour = datetime.datetime.fromtimestamp(future_ts).hour
        cycle_factor = cycle.get(hour, 1.0)
        predicted = trend_val * cycle_factor
        # clamp >= 0
        predicted = max(0, round(predicted))

        forecasts.append({
            "value": predicted,
            "recorded_at": future_ts,
            "is_forecast": True,
        })

    return forecasts
