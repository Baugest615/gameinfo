import { useState, useEffect } from 'react'
import './index.css'
import { API_BASE } from './config'
import Header from './components/Header'
import SteamPanel from './components/SteamPanel'
import TwitchPanel from './components/TwitchPanel'
import DiscussionPanel from './components/DiscussionPanel'
import NewsPanel from './components/NewsPanel'
import MobilePanel from './components/MobilePanel'
import WeeklyDigestPanel from './components/WeeklyDigestPanel'
import TrendModal from './components/TrendModal'

export default function App() {
    const [steamData, setSteamData] = useState([])
    const [trendTarget, setTrendTarget] = useState(null)
    const handleTrendClick = (id, name, source) => {
        setTrendTarget({ id, name, source })
    }

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
                <SteamPanel onTrendClick={handleTrendClick} />
                <TwitchPanel onTrendClick={handleTrendClick} />
                <DiscussionPanel />
                <NewsPanel />
                <MobilePanel />
                <WeeklyDigestPanel />
            </div>
            <TrendModal target={trendTarget} onClose={() => setTrendTarget(null)} />
        </div>
    )
}
