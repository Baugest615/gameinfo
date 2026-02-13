import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

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

export default function TrendModal({ target, onClose }) {
  const [days, setDays] = useState(7)
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!target) return
    setLoading(true)
    fetch(`${API_BASE}/api/history/${target.source}/${target.id}?days=${days}`)
      .then((r) => r.json())
      .then((json) => setData(json.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [target, days])

  if (!target) return null

  const color = SOURCE_COLOR[target.source] || '#3b82f6'
  const chartData = data.map((d) => ({ ...d, label: formatTime(d.recorded_at) }))

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
            <button className="trend-close-btn" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="trend-modal__body">
          {loading ? (
            <div className="loading-state">
              <div className="loading-spinner" />
              <span>載入中...</span>
            </div>
          ) : chartData.length < 2 ? (
            <div className="empty-state">
              <span className="empty-state__icon">📊</span>
              <span>歷史資料累積中，請稍後再查看</span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
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
                  itemStyle={{ color }}
                  formatter={(v) => [v.toLocaleString(), target.source === 'steam' ? '玩家數' : '觀看數']}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}
