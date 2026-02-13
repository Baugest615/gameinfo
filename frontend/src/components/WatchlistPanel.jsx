import { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function WatchlistPanel({ watchlist, removeFromWatchlist, onTrendClick }) {
  const [tab, setTab] = useState('steam')
  const [liveData, setLiveData] = useState({})

  const steamList = watchlist.filter((g) => g.source === 'steam')
  const twitchList = watchlist.filter((g) => g.source === 'twitch')
  const currentList = tab === 'steam' ? steamList : twitchList

  useEffect(() => {
    const fetchLive = async () => {
      const next = {}
      await Promise.all(
        watchlist.map(async (game) => {
          try {
            if (game.source === 'steam') {
              const r = await fetch(`${API_BASE}/api/steam/player-count/${game.id}`)
              const j = await r.json()
              next[`${game.source}:${game.id}`] = j.player_count
            }
          } catch {
            // 忽略個別失敗
          }
        })
      )
      setLiveData(next)
    }
    if (watchlist.length > 0) fetchLive()
  }, [watchlist])

  return (
    <div className="panel">
      <div className="panel__header">
        <div className="panel__title">
          <span className="panel__title-icon">⭐</span> 追蹤清單
        </div>
        <span className="panel__badge" style={{ color: '#eab308' }}>
          {watchlist.length} 項
        </span>
      </div>

      <div className="panel__tabs">
        <button
          className={`tab-btn ${tab === 'steam' ? 'tab-btn--active' : ''}`}
          onClick={() => setTab('steam')}
        >
          🔥 Steam ({steamList.length})
        </button>
        <button
          className={`tab-btn ${tab === 'twitch' ? 'tab-btn--active' : ''}`}
          onClick={() => setTab('twitch')}
        >
          📺 Twitch ({twitchList.length})
        </button>
      </div>

      <div className="panel__body">
        {currentList.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state__icon">⭐</span>
            <span>
              在 {tab === 'steam' ? 'Steam' : 'Twitch'} 面板點擊 ☆ 來收藏遊戲
            </span>
          </div>
        ) : (
          currentList.map((game) => {
            const liveKey = `${game.source}:${game.id}`
            const live = liveData[liveKey]
            return (
              <div key={liveKey} className="list-item">
                <div className="list-item__info">
                  <div className="list-item__name">{game.name}</div>
                  {live != null && (
                    <div className="list-item__meta">
                      {live.toLocaleString()} {game.source === 'steam' ? '玩家' : '觀看'}
                    </div>
                  )}
                </div>
                <div className="watchlist-item__actions">
                  <button
                    className="trend-btn"
                    title="查看趨勢"
                    onClick={() => onTrendClick(game.id, game.name, game.source)}
                  >
                    📈
                  </button>
                  <button
                    className="star-btn star-btn--active"
                    title="移除收藏"
                    onClick={() => removeFromWatchlist(game.id, game.source)}
                  >
                    ★
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
