# GameInfo System

A real-time game market sentiment tracking dashboard, styled after a Bloomberg Terminal. Aggregates live data from Steam, Twitch, Taiwanese gaming news outlets, community forums, and mobile app store rankings into a single dark-themed dashboard.

## Overview

GameInfo System provides a unified view of the gaming market by pulling data from multiple sources:

- **Steam** - Top games ranked by concurrent player count
- **Twitch** - Top games ranked by live viewer count
- **News** - Aggregated gaming news from GNN (Bahamut), 4Gamer, and UDN
- **Discussions** - Forum activity from Bahamut and PTT (Taiwan's largest gaming communities)
- **Mobile Rankings** - iOS App Store and Google Play game charts (Taiwan region)

All data is auto-refreshed on a schedule (every 10-30 minutes) and cached locally as JSON files.

## Tech Stack

| Layer | Technology |
|:---|:---|
| Frontend | React 19 + Vite 7 |
| Backend | Python FastAPI 0.115 |
| HTTP Client | httpx (async) |
| Scraping | BeautifulSoup4 + feedparser |
| Scheduling | APScheduler 3.10 |
| Cache | JSON flat files (no database) |
| Theme | Bloomberg Terminal Dark (Inter + JetBrains Mono) |

## Project Structure

```
gameinfo-system/
├── backend/
│   ├── main.py                 # FastAPI app, routes, CORS, lifespan
│   ├── scheduler.py            # Background jobs (10/30 min intervals)
│   ├── requirements.txt        # Python dependencies
│   ├── .env                    # Environment variables (API keys)
│   ├── cache/                  # Auto-generated JSON cache files
│   └── scrapers/
│       ├── steam_scraper.py    # Steam Web API
│       ├── twitch_scraper.py   # Twitch Helix API (OAuth)
│       ├── news_scraper.py     # GNN RSS + 4Gamer RSS + UDN scraping
│       ├── discussion_scraper.py # Bahamut + PTT forum scraping
│       └── mobile_scraper.py   # iTunes RSS API + Google Play scraping
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Root component (3x2 grid layout)
│   │   ├── index.css           # Bloomberg dark theme + all styles
│   │   └── components/
│   │       ├── Header.jsx      # Scrolling ticker + live clock
│   │       ├── SteamPanel.jsx  # Steam top games panel
│   │       ├── TwitchPanel.jsx # Twitch top games panel
│   │       ├── NewsPanel.jsx   # News feed panel
│   │       ├── DiscussionPanel.jsx # Forum discussion panel (4 tabs)
│   │       └── MobilePanel.jsx # Mobile rankings panel (3 tabs)
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm 9+

### 1. Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and fill in your Twitch credentials:
#   TWITCH_CLIENT_ID=your_client_id
#   TWITCH_CLIENT_SECRET=your_client_secret

# Start the API server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with Swagger docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

Open `http://localhost:5173` to view the dashboard.

### 3. Production Build

```bash
cd frontend
npm run build    # Build for production
npm run preview  # Preview the production build
```

## API Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| GET | `/` | Root info and endpoint directory |
| GET | `/api/health` | Health check |
| GET | `/api/steam/top-games` | Top 20 Steam games by concurrent players |
| GET | `/api/steam/player-count/{appid}` | Player count for a specific game |
| GET | `/api/twitch/top-games` | Top 20 Twitch games by viewer count |
| GET | `/api/news` | Aggregated gaming news (up to 50 items) |
| GET | `/api/discussions` | Forum activity (Bahamut boards/articles, PTT boards/articles) |
| GET | `/api/mobile/ios` | iOS App Store game rankings |
| GET | `/api/mobile/android` | Google Play game rankings |
| GET | `/api/mobile/all` | Combined iOS + Android rankings |

## Data Sources and Refresh Intervals

| Module | Source | Method | Interval |
|:---|:---|:---|:---:|
| Steam | Steam Web API | Free API (no key needed) | 10 min |
| Twitch | Twitch Helix API | OAuth client credentials | 10 min |
| News | GNN RSS, 4Gamer RSS, UDN | RSS + web scraping | 10 min |
| Discussions | Bahamut, PTT | HTML scraping | 10 min |
| iOS Rankings | Apple Marketing Tools | JSON API | 30 min |
| Android Rankings | Google Play | Web scraping | 30 min |

## Environment Variables

Create a `backend/.env` file (or copy from `.env.example`):

| Variable | Required | Default | Description |
|:---|:---:|:---:|:---|
| `TWITCH_CLIENT_ID` | Yes | — | Twitch Developer App Client ID |
| `TWITCH_CLIENT_SECRET` | Yes | — | Twitch Developer App Client Secret |
| `STEAM_API_KEY` | No | — | Steam API Key (most endpoints work without it) |
| `NEWS_MAX_COUNT` | No | 50 | Maximum news articles to retain |
| `NEWS_UPDATE_INTERVAL` | No | 10 | News update interval in minutes |

To obtain Twitch API credentials:
1. Go to https://dev.twitch.tv/console
2. Log in and create a new Application
3. Copy the Client ID and Client Secret

## Architecture

**Backend** - FastAPI serves a REST API. Each scraper module fetches live data from its source and writes results to a JSON cache file. On failure, cached data is returned as a fallback. APScheduler runs background jobs on fixed intervals.

**Frontend** - React SPA with a Bloomberg Terminal dark theme. Each panel component polls its corresponding API endpoint every 10 minutes via `setInterval`. The header features a horizontally scrolling ticker showing Steam top-10 data and a live clock.

**Caching** - No database is used. All data is stored as JSON files under `backend/cache/`. This keeps the system simple and stateless with zero external dependencies.

## Roadmap

- **Phase 1** (Done) - Steam player counts, news aggregation, PTT discussions, Bloomberg-style UI
- **Phase 2** (Done) - Bahamut forums, iOS rankings, Twitch integration, mobile rankings panel
- **Phase 3** (Planned) - Google Trends integration, NLP sentiment analysis, historical trend charts, custom game watchlists, AI-powered popularity predictions, deployment to Vercel + Railway

## License

MIT
