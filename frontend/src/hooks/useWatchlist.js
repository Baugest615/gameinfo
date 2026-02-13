import { useState, useCallback } from 'react'

const STORAGE_KEY = 'gameinfo_watchlist'

function loadWatchlist() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

function saveWatchlist(list) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
}

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState(loadWatchlist)

  const addToWatchlist = useCallback((game) => {
    setWatchlist((prev) => {
      if (prev.some((g) => g.id === game.id && g.source === game.source)) return prev
      const next = [...prev, { ...game, addedAt: Date.now() }]
      saveWatchlist(next)
      return next
    })
  }, [])

  const removeFromWatchlist = useCallback((id, source) => {
    setWatchlist((prev) => {
      const next = prev.filter((g) => !(g.id === id && g.source === source))
      saveWatchlist(next)
      return next
    })
  }, [])

  const isWatched = useCallback(
    (id, source) => watchlist.some((g) => g.id === id && g.source === source),
    [watchlist]
  )

  return { watchlist, addToWatchlist, removeFromWatchlist, isWatched }
}
