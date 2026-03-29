import { useState, useEffect, useRef } from 'react'

export default function Header({ steamData }) {
  const [time, setTime] = useState('')
  const trackRef = useRef(null)

  useEffect(() => {
    const update = () => {
      const now = new Date()
      setTime(now.toLocaleString('zh-TW', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
      }))
    }
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [])

  const tickerItems = (steamData || []).slice(0, 10).map(g => ({
    name: g.name,
    value: g.current_players?.toLocaleString() || '—',
  }))

  return (
    <header className="header">
      <div className="header__logo">
        <span className="header__logo-icon">🎮</span>
        <span>GAMEINFO</span>
      </div>

      <div className="header__ticker">
        <div className="ticker-track" ref={trackRef}>
          {tickerItems.length === 0 ? (
            <div className="ticker-item">
              <span className="ticker-item__name">載入中...</span>
            </div>
          ) : (
            [...tickerItems, ...tickerItems].map((item, i) => (
              <div key={i} className="ticker-item">
                <span className="ticker-item__name">{item.name}</span>
                <span className="ticker-item__value">
                  {item.value}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="header__time-area">
        <div className="header__time">{time}</div>
        <div className="header__credit">created by 法蘭奇</div>
      </div>
    </header>
  )
}
