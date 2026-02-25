import { useState, useEffect } from 'react'
import { API_BASE } from '../config'

const TABS = [
    { key: 'all', label: '全部', source: null },
    { key: 'gnn', label: 'GNN', source: '巴哈姆特 GNN' },
    { key: '4gamers', label: '4Gamers', source: '4Gamers TW' },
    { key: 'udn', label: 'UDN', source: 'UDN 遊戲角落' },
]

export default function NewsPanel() {
    const [news, setNews] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [totalCount, setTotalCount] = useState(0)
    const [sourceCounts, setSourceCounts] = useState({})
    const [activeTab, setActiveTab] = useState('all')

    const fetchData = async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/news`)
            const json = await resp.json()
            setNews(json.data?.news || [])
            setTotalCount(json.data?.total_count || 0)
            setSourceCounts(json.data?.source_counts || {})
            setError(null)
        } catch (err) {
            console.error('[News] Fetch error:', err)
            if (news.length === 0) setError('新聞載入失敗')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
        const timer = setInterval(fetchData, 10 * 60 * 1000)
        return () => clearInterval(timer)
    }, [])

    const activeSource = TABS.find(t => t.key === activeTab)?.source
    const filteredNews = activeSource
        ? news.filter(item => item.source === activeSource)
        : news

    const getTabCount = (tab) => {
        if (!tab.source) return totalCount
        return sourceCounts[tab.source] || 0
    }

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
                <span className="panel__badge panel__badge--count">
                    {filteredNews.length}
                </span>
            </div>
            <div className="tab-switcher">
                {TABS.map(tab => (
                    <button
                        key={tab.key}
                        className={`tab-btn ${activeTab === tab.key ? 'tab-btn--active' : ''}`}
                        onClick={() => setActiveTab(tab.key)}
                    >
                        {tab.label}
                        <span className="news-tab__count">{getTabCount(tab)}</span>
                    </button>
                ))}
            </div>
            <div className="panel__body">
                {error ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">&#x26A0;&#xFE0F;</span>
                        <span>{error}</span>
                    </div>
                ) : filteredNews.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">📰</span>
                        <span>暫無新聞</span>
                    </div>
                ) : (
                    filteredNews.map((item, i) => (
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
