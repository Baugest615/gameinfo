import { useState, useEffect } from 'react';

const TABS = [
    { key: 'bahamut_boards', label: '巴哈熱門版' },
    { key: 'ptt_boards', label: 'PTT 熱門版' },
    { key: 'bahamut_articles', label: '巴哈熱議' },
    { key: 'ptt_articles', label: 'PTT 熱文' },
];

export default function DiscussionPanel() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('bahamut_boards');
    const [sentimentSummary, setSentimentSummary] = useState(null);

    const sentimentIcon = (label) => {
        if (label === 'positive') return '↑ 正面';
        if (label === 'negative') return '↓ 負面';
        return '→ 中性';
    };

    const isArticleTab = (tab) => tab === 'bahamut_articles' || tab === 'ptt_articles';

    useEffect(() => {
        fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}/api/discussions`)
            .then(r => r.json())
            .then(d => {
                setData(d.data);
                setSentimentSummary(d.data?.sentiment_summary || null);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const currentItems = data ? (data[activeTab] || []) : [];

    return (
        <div className="panel">
            <div className="panel__header">
                <div className="panel__title">
                    <span className="panel__title-icon">💬</span>
                    討論聲量
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {sentimentSummary && (
                        <span className={`panel__sentiment panel__sentiment--${sentimentSummary.label}`}>
                            {sentimentIcon(sentimentSummary.label)}
                        </span>
                    )}
                    <span className="panel__badge panel__badge--count">
                        {data?.total_count || 0}
                    </span>
                </div>
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
                        <span>載入討論數據中...</span>
                    </div>
                ) : currentItems.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-state__icon">📭</span>
                        <span>尚無數據</span>
                    </div>
                ) : (
                    currentItems.map((item, i) => (
                        <a
                            key={i}
                            className="list-item"
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            <span className={`list-item__rank ${(item.rank || i + 1) <= 3 ? 'list-item__rank--top3' : ''}`}>
                                {item.rank || i + 1}
                            </span>
                            <div className="list-item__info">
                                <div className="list-item__name">
                                    {item.title || item.name}
                                </div>
                                <div className="list-item__meta">
                                    {/* Tab-specific subtitles */}
                                    {activeTab === 'ptt_boards' && (
                                        <>{item.category && `${item.category} · `}{item.title}</>
                                    )}
                                    {activeTab === 'bahamut_boards' && '遊戲討論版'}
                                    {activeTab === 'bahamut_articles' && item.source}
                                    {activeTab === 'ptt_articles' && item.source}
                                </div>
                            </div>
                            {/* Sentiment badge (article tabs only) */}
                            {isArticleTab(activeTab) && item.sentiment && (
                                <span className={`sentiment-badge sentiment-badge--${item.sentiment.label}`}>
                                    {item.sentiment.label === 'positive' ? '正面' : item.sentiment.label === 'negative' ? '負面' : '中性'}
                                </span>
                            )}
                            {/* Popularity / badge */}
                            {activeTab === 'ptt_boards' && item.popularity > 0 && (
                                <span className="list-item__value list-item__value--hot">
                                    🔥 {item.popularity}
                                </span>
                            )}
                            {activeTab === 'ptt_articles' && item.popularity && (
                                <span className="list-item__value">
                                    {item.popularity === '爆' ? '🔥 爆' : `👍 ${item.popularity}`}
                                </span>
                            )}
                        </a>
                    ))
                )}
            </div>
        </div>
    );
}
