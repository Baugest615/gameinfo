import { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const TABS = [
  { key: 'gaming', label: '🎮 遊戲' },
  { key: 'anime', label: '🌸 二次元' },
]

export default function GoogleTrendsPanel() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('gaming')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/google-trends`)
        const json = await resp.json()
        setData(json.data || null)
      } catch (err) {
        console.error('[GoogleTrends] Fetch error:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
    const timer = setInterval(fetchData, 10 * 60 * 1000)
    return () => clearInterval(timer)
  }, [])

  const currentItems = data ? (data[activeTab] || []) : []

  return (
    <div className="panel">
      <div className="panel__header">
        <div className="panel__title">
          <span className="panel__title-icon">📊</span> GOOGLE 熱搜趨勢
        </div>
        <span className="panel__badge" style={{ color: '#4285f4' }}>
          {data ? `${data.total_count || 0} 筆` : '—'}
        </span>
      </div>

      <div className="panel__tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`tab-btn ${activeTab === tab.key ? 'tab-btn--active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label} ({activeTab === tab.key ? currentItems.length : (data?.[tab.key]?.length || 0)})
          </button>
        ))}
      </div>

      <div className="panel__body">
        {loading ? (
          <div className="loading-state">
            <div className="loading-spinner" />
            <span>載入熱搜數據中...</span>
          </div>
        ) : currentItems.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state__icon">📊</span>
            <span>尚無{activeTab === 'gaming' ? '遊戲' : '二次元'}相關熱搜</span>
          </div>
        ) : (
          currentItems.map((item, i) => (
            <div key={`${item.title}-${i}`} className="list-item">
              <span className={`list-item__rank ${i < 3 ? 'list-item__rank--top3' : ''}`}>
                {i + 1}
              </span>
              <div className="list-item__info">
                <div className="list-item__name">{item.title}</div>
                <div className="list-item__meta">
                  {item.related?.slice(0, 2).join(' · ') || ''}
                </div>
              </div>
              <div className="list-item__value" style={{ color: '#4285f4' }}>
                {item.traffic || '—'}
              </div>
              {item.articles?.[0]?.url && (
                <a
                  href={item.articles[0].url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="trend-btn"
                  title={item.articles[0].title || '相關新聞'}
                >
                  📰
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
