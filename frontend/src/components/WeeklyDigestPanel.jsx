import { useState, useEffect } from 'react'
import { API_BASE } from '../config'

const TAG_LABELS = {
    ad: { icon: '📢', label: '廣告' },
    collab: { icon: '🤝', label: '聯名' },
    event: { icon: '🎉', label: '活動' },
    news: { icon: '📄', label: '新聞' },
}

const FILTER_TABS = [
    { key: 'all', label: '全部' },
    { key: 'ad', label: '📢 廣告' },
    { key: 'collab', label: '🤝 聯名' },
    { key: 'event', label: '🎉 活動' },
]

export default function WeeklyDigestPanel() {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [activeFilter, setActiveFilter] = useState('all')
    const [expandedGame, setExpandedGame] = useState(null)

    useEffect(() => {
        const fetchData = async () => {
            try {
                const resp = await fetch(`${API_BASE}/api/weekly-digest`)
                const json = await resp.json()
                setData(json.data || null)
                setError(null)
            } catch (err) {
                console.error('[WeeklyDigest] Fetch error:', err)
                if (!data) setError('摘要載入失敗')
            } finally {
                setLoading(false)
            }
        }
        fetchData()
        // 每周摘要不需要頻繁刷新，30 分鐘一次即可
        const timer = setInterval(fetchData, 30 * 60 * 1000)
        return () => clearInterval(timer)
    }, [])

    const digest = data?.digest || []

    // 根據 filter 篩選有相關內容的遊戲
    const filteredDigest = activeFilter === 'all'
        ? digest
        : digest.filter(g => g.items?.some(item => item.tags?.includes(activeFilter)))
            .map(g => ({
                ...g,
                items: g.items.filter(item => item.tags?.includes(activeFilter)),
                item_count: g.items.filter(item => item.tags?.includes(activeFilter)).length,
            }))

    const formatDate = (dateStr) => {
        if (!dateStr) return ''
        try {
            const d = new Date(dateStr)
            return d.toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit' })
        } catch {
            return ''
        }
    }

    if (loading) {
        return (
            <div className="panel">
                <div className="panel__header">
                    <div className="panel__title">
                        <span className="panel__title-icon">📋</span> 每周行銷摘要
                    </div>
                </div>
                <div className="loading-state">
                    <div className="loading-spinner" />
                    <span>載入摘要中...</span>
                </div>
            </div>
        )
    }

    return (
        <div className="panel">
            <div className="panel__header">
                <div className="panel__title">
                    <span className="panel__title-icon">📋</span> 每周行銷摘要
                </div>
                <span className="panel__badge panel__badge--count">
                    {data?.period
                        ? `${data.period.start?.slice(5)} ~ ${data.period.end?.slice(5)}`
                        : '—'}
                </span>
            </div>
            <div className="tab-switcher">
                {FILTER_TABS.map(tab => (
                    <button
                        key={tab.key}
                        className={`tab-btn ${activeFilter === tab.key ? 'tab-btn--active' : ''}`}
                        onClick={() => setActiveFilter(tab.key)}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>
            <div className="panel__body">
                {error ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">&#x26A0;&#xFE0F;</span>
                        <span>{error}</span>
                    </div>
                ) : filteredDigest.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">📋</span>
                        <span>本周尚無行銷摘要</span>
                    </div>
                ) : (
                    filteredDigest.map((game) => (
                        <div key={game.game} className="digest-game">
                            <div
                                className="digest-game__header"
                                onClick={() => setExpandedGame(
                                    expandedGame === game.game ? null : game.game
                                )}
                            >
                                <div className="digest-game__info">
                                    <span className="digest-game__name">{game.game}</span>
                                    <div className="digest-game__tags">
                                        {game.tag_counts?.ad > 0 && (
                                            <span className="digest-tag digest-tag--ad">
                                                📢{game.tag_counts.ad}
                                            </span>
                                        )}
                                        {game.tag_counts?.collab > 0 && (
                                            <span className="digest-tag digest-tag--collab">
                                                🤝{game.tag_counts.collab}
                                            </span>
                                        )}
                                        {game.tag_counts?.event > 0 && (
                                            <span className="digest-tag digest-tag--event">
                                                🎉{game.tag_counts.event}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <span className="digest-game__count">
                                    {game.item_count} 筆
                                    <span className="digest-game__arrow">
                                        {expandedGame === game.game ? '▾' : '▸'}
                                    </span>
                                </span>
                            </div>
                            {expandedGame === game.game && (
                                <div className="digest-game__items">
                                    {game.items?.map((item, i) => (
                                        <a
                                            key={`${item.url}-${i}`}
                                            href={item.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="digest-item"
                                        >
                                            <div className="digest-item__tags">
                                                {item.tags?.map(t => (
                                                    <span key={t} className={`digest-tag digest-tag--${t}`}>
                                                        {TAG_LABELS[t]?.icon}
                                                    </span>
                                                ))}
                                            </div>
                                            <div className="digest-item__content">
                                                <div className="digest-item__title">{item.title}</div>
                                                <div className="digest-item__meta">
                                                    <span className="digest-item__source">{item.source}</span>
                                                    <span className="digest-item__date">
                                                        {formatDate(item.published_at)}
                                                    </span>
                                                </div>
                                            </div>
                                        </a>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    )
}
