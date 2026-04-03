import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'
import { API_BASE } from '../config'

function formatTime(ts) {
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function formatValue(v) {
  if (v >= 1000000) return `${(v / 1000000).toFixed(1)}M`
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`
  return v
}

const SOURCE_LABEL = { steam: 'Steam', twitch: 'Twitch' }
const SOURCE_COLOR = { steam: '#22c55e', twitch: '#a855f7' }
const FORECAST_COLOR = '#f59e0b'

export default function TrendModal({ target, onClose }) {
  const [days, setDays] = useState(7)
  const [data, setData] = useState([])
  const [forecast, setForecast] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForecast, setShowForecast] = useState(false)

  // ESC 鍵關閉 Modal
  useEffect(() => {
    if (!target) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [target, onClose])

  useEffect(() => {
    if (!target) return
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    fetch(`${API_BASE}/api/history/${target.source}/${target.id}?days=${days}&forecast=true`, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((json) => {
        setData(json.data || [])
        setForecast(json.forecast || [])
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setData([])
        setForecast([])
        setError('趨勢資料載入失敗')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [target, days])

  if (!target) return null

  const color = SOURCE_COLOR[target.source] || '#3b82f6'
  const valueLabel = target.source === 'steam' ? '玩家數' : '觀看數'

  // 合併歷史 + 預測資料
  const chartData = data.map((d) => ({ ...d, label: formatTime(d.recorded_at), value: d.value }))

  let mergedData = chartData
  if (showForecast && forecast.length > 0 && chartData.length > 0) {
    // bridge: 最後一個歷史點也設定 forecast 值，讓虛線接起來
    const lastHistory = chartData[chartData.length - 1]
    const bridged = { ...lastHistory, forecast: lastHistory.value }
    const forecastPoints = forecast.map((d) => ({
      label: formatTime(d.recorded_at),
      recorded_at: d.recorded_at,
      forecast: d.value,
    }))
    mergedData = [
      ...chartData.slice(0, -1),
      bridged,
      ...forecastPoints,
    ]
  }

  return (
    <div className="trend-modal-overlay" onClick={onClose}>
      <div className="trend-modal" onClick={(e) => e.stopPropagation()}>
        <div className="trend-modal__header">
          <div className="trend-modal__title">
            <span className="trend-modal__source-badge" style={{ color }}>
              {SOURCE_LABEL[target.source]}
            </span>
            {target.name}
          </div>
          <div className="trend-modal__controls">
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                className={`trend-day-btn ${days === d ? 'trend-day-btn--active' : ''}`}
                onClick={() => setDays(d)}
              >
                {d}天
              </button>
            ))}
            <button
              className={`forecast-btn ${showForecast ? 'forecast-btn--active' : ''}`}
              onClick={() => setShowForecast((v) => !v)}
              title="AI 預測未來 24 小時"
            >
              🔮 預測
            </button>
            <button className="trend-close-btn" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="trend-modal__body">
          {loading ? (
            <div className="loading-state">
              <div className="loading-spinner" />
              <span>載入中...</span>
            </div>
          ) : error ? (
            <div className="empty-state">
              <span className="empty-state__icon">&#x26A0;&#xFE0F;</span>
              <span>{error}</span>
            </div>
          ) : chartData.length < 2 ? (
            <div className="empty-state">
              <span className="empty-state__icon">📊</span>
              <span>歷史資料累積中，請稍後再查看</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={mergedData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: '#64748b', fontSize: 11 }}
                  interval="preserveStartEnd"
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#64748b', fontSize: 11 }}
                  tickFormatter={formatValue}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                />
                <Tooltip
                  contentStyle={{ background: '#151d2e', border: '1px solid #1e293b', borderRadius: 6 }}
                  labelStyle={{ color: '#94a3b8', fontSize: 12 }}
                  formatter={(v, name) => {
                    if (v == null) return ['—', name === 'forecast' ? `預測${valueLabel}` : valueLabel]
                    if (name === 'forecast') return [v.toLocaleString(), `預測${valueLabel}`]
                    return [v.toLocaleString(), valueLabel]
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls={false}
                />
                {showForecast && forecast.length > 0 && (
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    stroke={FORECAST_COLOR}
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    strokeOpacity={0.7}
                    dot={false}
                    activeDot={{ r: 4 }}
                    connectNulls={false}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}
