import { useState, useEffect } from 'react'
import './index.css'
import Header from './components/Header'
import SteamPanel from './components/SteamPanel'
import TwitchPanel from './components/TwitchPanel'
import DiscussionPanel from './components/DiscussionPanel'
import NewsPanel from './components/NewsPanel'
import MobilePanel from './components/MobilePanel'

const API_BASE = 'http://localhost:8000'

export default function App() {
    const [steamData, setSteamData] = useState([])

    // 取得 Steam 資料供 Header ticker 使用
    useEffect(() => {
        const fetchSteam = async () => {
            try {
                const resp = await fetch(`${API_BASE}/api/steam/top-games`)
                const json = await resp.json()
                setSteamData(json.data || [])
            } catch (err) {
                console.error('[App] Steam fetch for ticker:', err)
            }
        }
        fetchSteam()
        const timer = setInterval(fetchSteam, 10 * 60 * 1000)
        return () => clearInterval(timer)
    }, [])

    return (
        <div className="app">
            <Header steamData={steamData} />
            <div className="main-grid">
                <SteamPanel />
                <TwitchPanel />
                <DiscussionPanel />
                <NewsPanel />
                <MobilePanel />
                {/* Phase 3 預留位置 */}
                <div className="panel">
                    <div className="panel__header">
                        <div className="panel__title">
                            <span className="panel__title-icon">📊</span> 搜尋趨勢 (Coming Soon)
                        </div>
                    </div>
                    <div className="empty-state">
                        <span className="empty-state__icon">🔮</span>
                        <span>Phase 3 — Google Trends 整合</span>
                    </div>
                </div>
            </div>
        </div>
    )
}
