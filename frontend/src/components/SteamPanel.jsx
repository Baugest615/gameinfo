import { useState, useEffect } from 'react'
import { API_BASE } from '../config'

export default function SteamPanel({ onTrendClick }) {
    const [games, setGames] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchData = async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/steam/top-games`)
            const json = await resp.json()
            setGames(json.data || [])
            setError(null)
        } catch (err) {
            console.error('[Steam] Fetch error:', err)
            if (games.length === 0) setError('Steam 資料載入失敗')
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
                        <span className="panel__title-icon">🔥</span> STEAM 熱門遊戲
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
                    <span className="panel__title-icon">🔥</span> STEAM 熱門遊戲
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
                        <span className="empty-state__icon">🎮</span>
                        <span>暫無資料</span>
                    </div>
                ) : (
                    games.map((game, i) => (
                            <div key={game.appid || i} className="list-item">
                                <span className={`list-item__rank ${i < 3 ? 'list-item__rank--top3' : ''}`}>
                                    {i + 1}
                                </span>
                                <div className="list-item__info">
                                    <div className="list-item__name">{game.name}</div>
                                    <div className="list-item__meta">AppID: {game.appid}</div>
                                </div>
                                <div className="list-item__value">
                                    {game.current_players?.toLocaleString() || '—'}
                                </div>
                                <button
                                    className="trend-btn"
                                    title="查看趨勢"
                                    onClick={() => onTrendClick?.(String(game.appid), game.name, 'steam')}
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
