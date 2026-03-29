import { useState, useEffect } from 'react'
import { API_BASE } from '../config'

export default function TwitchPanel({ onTrendClick }) {
    const [games, setGames] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchData = async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/twitch/top-games`)
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
            const json = await resp.json()
            setGames(json.data || [])
            setError(null)
        } catch (err) {
            console.error('[Twitch] Fetch error:', err)
            setGames(prev => {
                if (prev.length === 0) setError('Twitch 資料載入失敗')
                return prev
            })
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
                {error ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">&#x26A0;&#xFE0F;</span>
                        <span>{error}</span>
                    </div>
                ) : games.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">📺</span>
                        <span>請設定 Twitch API Key</span>
                    </div>
                ) : (
                    games.map((game, i) => (
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
                                <button
                                    className="trend-btn"
                                    title="查看趨勢"
                                    onClick={() => onTrendClick?.(String(game.id), game.name, 'twitch')}
                                >
                                    📈
                                </button>
                            </div>
                    ))
                )}
            </div>
        </div>
    )
}
