import { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function NewsPanel() {
    const [news, setNews] = useState([])
    const [loading, setLoading] = useState(true)
    const [totalCount, setTotalCount] = useState(0)
    const [sentimentSummary, setSentimentSummary] = useState(null)

    const fetchData = async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/news`)
            const json = await resp.json()
            setNews(json.data?.news || [])
            setTotalCount(json.data?.total_count || 0)
            setSentimentSummary(json.data?.sentiment_summary || null)
        } catch (err) {
            console.error('[News] Fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    const sentimentIcon = (label) => {
        if (label === 'positive') return '↑ 正面'
        if (label === 'negative') return '↓ 負面'
        return '→ 中性'
    }

    useEffect(() => {
        fetchData()
        const timer = setInterval(fetchData, 10 * 60 * 1000)
        return () => clearInterval(timer)
    }, [])

    const getSourceClass = (source) => {
        if (source?.includes('GNN')) return 'news-item__source--gnn'
        if (source?.includes('4Gamer')) return 'news-item__source--4gamer'
        if (source?.includes('UDN')) return 'news-item__source--udn'
        return ''
    }

    const formatTime = (timestamp) => {
        if (!timestamp) return ''
        try {
            const date = new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp)
            return date.toLocaleString('zh-TW', {
                month: '2-digit', day: '2-digit',
                hour: '2-digit', minute: '2-digit', hour12: false,
            })
        } catch {
            return ''
        }
    }

    if (loading) {
        return (
            <div className="panel">
                <div className="panel__header">
                    <div className="panel__title">
                        <span className="panel__title-icon">📰</span> 即時新聞
                    </div>
                </div>
                <div className="loading-state">
                    <div className="loading-spinner" />
                    <span>載入中...</span>
                </div>
            </div>
        )
    }

    return (
        <div className="panel">
            <div className="panel__header">
                <div className="panel__title">
                    <span className="panel__title-icon">📰</span> 即時新聞
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {sentimentSummary && (
                        <span className={`panel__sentiment panel__sentiment--${sentimentSummary.label}`}>
                            {sentimentIcon(sentimentSummary.label)}
                        </span>
                    )}
                    <span className="panel__badge panel__badge--count">
                        {totalCount}/50
                    </span>
                </div>
            </div>
            <div className="panel__body">
                {news.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">📰</span>
                        <span>暫無新聞</span>
                    </div>
                ) : (
                    news.map((item, i) => (
                        <a
                            key={item.id || i}
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="news-item"
                        >
                            <div className="news-item__title">{item.title}</div>
                            <div className="news-item__footer">
                                <span className={`news-item__source ${getSourceClass(item.source)}`}>
                                    {item.source_icon} {item.source}
                                </span>
                                {item.sentiment && (
                                    <span className={`sentiment-badge sentiment-badge--${item.sentiment.label}`}>
                                        {item.sentiment.label === 'positive' ? '正面' : item.sentiment.label === 'negative' ? '負面' : '中性'}
                                    </span>
                                )}
                                <span className="news-item__time">
                                    {formatTime(item.published_at || item.fetched_at)}
                                </span>
                            </div>
                        </a>
                    ))
                )}
            </div>
        </div>
    )
}
