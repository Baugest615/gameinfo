import { Component } from 'react'

export default class ErrorBoundary extends Component {
    constructor(props) {
        super(props)
        this.state = { hasError: false, error: null }
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error }
    }

    componentDidCatch(error, errorInfo) {
        console.error(`[ErrorBoundary] ${this.props.name || 'Unknown'} crashed:`, error, errorInfo)
    }

    componentDidUpdate(prevProps) {
        // key-based reset: 當 resetKey 變化時自動清除錯誤狀態
        if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
            this.setState({ hasError: false, error: null })
        }
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null })
        this.props.onRetry?.()
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="panel">
                    <div className="panel__header">
                        <div className="panel__title">
                            <span className="panel__title-icon">&#x26A0;&#xFE0F;</span>
                            {this.props.name || '模組'}
                        </div>
                    </div>
                    <div className="panel__body">
                        <div className="empty-state">
                            <span className="empty-state__icon">&#x1F6A7;</span>
                            <span>此模組發生錯誤，其他模組不受影響</span>
                            <button
                                className="retry-btn"
                                onClick={this.handleRetry}
                                style={{
                                    marginTop: '0.5rem',
                                    padding: '0.4rem 1rem',
                                    border: '1px solid var(--border-color, #444)',
                                    borderRadius: '4px',
                                    background: 'transparent',
                                    color: 'inherit',
                                    cursor: 'pointer',
                                    fontSize: '0.85rem',
                                }}
                            >
                                重試
                            </button>
                        </div>
                    </div>
                </div>
            )
        }

        return this.props.children
    }
}
