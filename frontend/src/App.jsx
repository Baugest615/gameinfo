import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from './config'
import Header from './components/Header'
import ErrorBoundary from './components/ErrorBoundary'
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
    const handleTrendClose = useCallback(() => setTrendTarget(null), [])

    // 取得 Steam 資料供 Header ticker + SteamPanel 共用
    useEffect(() => {
        const controller = new AbortController()
        const fetchSteam = async () => {
            try {
                const resp = await fetch(`${API_BASE}/api/steam/top-games`, { signal: controller.signal })
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
                const json = await resp.json()
                setSteamData(json.data || [])
            } catch (err) {
                if (err.name === 'AbortError') return
                console.error('[App] Steam fetch for ticker:', err)
            }
        }
        fetchSteam()
        const timer = setInterval(fetchSteam, 10 * 60 * 1000)
        return () => {
            controller.abort()
            clearInterval(timer)
        }
    }, [])

    return (
        <div className="app">
            <Header steamData={steamData} />
            <div className="main-grid">
                <ErrorBoundary name="STEAM 熱門遊戲">
                    <SteamPanel steamData={steamData} onTrendClick={handleTrendClick} />
                </ErrorBoundary>
                <ErrorBoundary name="TWITCH 中文直播熱度">
                    <TwitchPanel onTrendClick={handleTrendClick} />
                </ErrorBoundary>
                <ErrorBoundary name="討論聲量">
                    <DiscussionPanel />
                </ErrorBoundary>
                <ErrorBoundary name="即時新聞">
                    <NewsPanel />
                </ErrorBoundary>
                <ErrorBoundary name="手遊排行">
                    <MobilePanel />
                </ErrorBoundary>
                <ErrorBoundary name="每周摘要">
                    <WeeklyDigestPanel />
                </ErrorBoundary>
            </div>
            <TrendModal target={trendTarget} onClose={handleTrendClose} />
        </div>
    )
}
