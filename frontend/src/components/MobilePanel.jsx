import { useState, useEffect } from 'react';
import { API_BASE } from '../config';

const TABS = [
    { key: 'ios_free', label: 'iOS 免費' },
    { key: 'android_free', label: 'Android 免費' },
    { key: 'android_grossing', label: 'Android 營收' },
];

export default function MobilePanel() {
    const [iosData, setIosData] = useState(null);
    const [androidData, setAndroidData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('ios_free');

    useEffect(() => {
        const controller = new AbortController();
        Promise.all([
            fetch(`${API_BASE}/api/mobile/ios`, { signal: controller.signal }).then(r => {
                if (!r.ok) throw new Error(`iOS HTTP ${r.status}`);
                return r.json();
            }),
            fetch(`${API_BASE}/api/mobile/android`, { signal: controller.signal }).then(r => {
                if (!r.ok) throw new Error(`Android HTTP ${r.status}`);
                return r.json();
            }),
        ])
            .then(([ios, android]) => {
                setIosData(ios.data);
                setAndroidData(android.data);
                setError(null);
                setLoading(false);
            })
            .catch(err => {
                if (err.name === 'AbortError') return;
                setError('手遊排行載入失敗');
                setLoading(false);
            });
        return () => controller.abort();
    }, []);

    const getItems = () => {
        if (activeTab === 'ios_free') return iosData?.free || [];
        if (activeTab === 'android_free') return androidData?.free || [];
        if (activeTab === 'android_grossing') return androidData?.grossing || [];
        return [];
    };

    const items = getItems();

    return (
        <div className="panel">
            <div className="panel__header">
                <div className="panel__title">
                    <span className="panel__title-icon">📱</span>
                    手遊排行
                </div>
                <span className="panel__badge panel__badge--count">
                    {items.length || '—'}
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
                    </button>
                ))}
            </div>
            <div className="panel__body">
                {loading ? (
                    <div className="loading-state">
                        <div className="loading-spinner" />
                        <span>載入排行數據中...</span>
                    </div>
                ) : error ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">&#x26A0;&#xFE0F;</span>
                        <span>{error}</span>
                    </div>
                ) : items.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">📭</span>
                        <span>尚無數據</span>
                    </div>
                ) : (
                    items.map((app, i) => (
                        <a
                            key={app.id || i}
                            className="list-item"
                            href={app.url}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            <span className={`list-item__rank ${(app.rank ?? i + 1) <= 3 ? 'list-item__rank--top3' : ''}`}>
                                {app.rank ?? i + 1}
                            </span>
                            {app.icon && (
                                <img
                                    className="list-item__icon"
                                    src={app.icon}
                                    alt={app.name}
                                    loading="lazy"
                                />
                            )}
                            <div className="list-item__info">
                                <div className="list-item__name">{app.name}</div>
                                <div className="list-item__meta">
                                    {typeof app.genres === 'string'
                                        ? app.genres
                                        : Array.isArray(app.genres) && app.genres.length > 0
                                            ? app.genres.join(' · ')
                                            : app.developer || app.chart || ''}
                                    {app.score > 0 && ` ⭐ ${app.score}`}
                                </div>
                            </div>
                            {app.installs && (
                                <span className="list-item__value" style={{ fontSize: '10px' }}>
                                    {app.installs}
                                </span>
                            )}
                            <span className={`mobile-item__chart-badge ${activeTab.includes('grossing') ? 'mobile-item__chart-badge--grossing' : 'mobile-item__chart-badge--free'
                                }`}>
                                {app.chart || (activeTab.includes('ios') ? 'iOS' : 'Android')}
                            </span>
                        </a>
                    ))
                )}
            </div>
        </div>
    );
}
