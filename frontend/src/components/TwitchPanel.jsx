import { useState, useEffect } from 'react'
import { useWatchlist } from '../hooks/useWatchlist'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function TwitchPanel({ onTrendClick }) {
    const [games, setGames] = useState([])
    const [loading, setLoading] = useState(true)
    const { isWatched, addToWatchlist, removeFromWatchlist } = useWatchlist()

    const fetchData = async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/twitch/top-games`)
            const json = await resp.json()
            setGames(json.data || [])
        } catch (err) {
            console.error('[Twitch] Fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
        const timer = setInterval(fetchData, 10 * 60 * 1000)
        return () => clearInterval(timer)
    }, [])

    if (loading) {
        return (
            <div className="panel">
                <div className="panel__header">
                    <div className="panel__title">
                        <span className="panel__title-icon">📺</span> TWITCH 中文直播熱度
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
                    <span className="panel__title-icon">📺</span> TWITCH 中文直播熱度
                </div>
                <span className="panel__badge panel__badge--live">● LIVE</span>
            </div>
            <div className="panel__body">
                {games.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">📺</span>
                        <span>請設定 Twitch API Key</span>
                    </div>
                ) : (
                    games.map((game, i) => {
                        const watched = isWatched(String(game.id), 'twitch')
                        return (
                            <div key={game.id || i} className="list-item">
                                <span className={`list-item__rank ${i < 3 ? 'list-item__rank--top3' : ''}`}>
                                    {i + 1}
                                </span>
                                {game.box_art_url && (
                                    <img className="list-item__icon" src={game.box_art_url} alt="" />
                                )}
                                <div className="list-item__info">
                                    <div className="list-item__name">{game.name}</div>
                                </div>
                                <div className="list-item__value">
                                    {game.viewer_count ? `${game.viewer_count.toLocaleString()} 👁` : '—'}
                                </div>
                                <div className="list-item__actions">
                                    <button
                                        className="trend-btn"
                                        title="查看趨勢"
                                        onClick={() => onTrendClick?.(String(game.id), game.name, 'twitch')}
                                    >
                                        📈
                                    </button>
                                    <button
                                        className={`star-btn ${watched ? 'star-btn--active' : ''}`}
                                        title={watched ? '取消收藏' : '加入追蹤'}
                                        onClick={() =>
                                            watched
                                                ? removeFromWatchlist(String(game.id), 'twitch')
                                                : addToWatchlist({ id: String(game.id), name: game.name, source: 'twitch' })
                                        }
                                    >
                                        {watched ? '★' : '☆'}
                                    </button>
                                </div>
                            </div>
                        )
                    })
                )}
            </div>
        </div>
    )
}
