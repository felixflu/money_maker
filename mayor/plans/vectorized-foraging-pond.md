# Crypto Dashboard — Implementation Plan

## Context

Build a personal crypto transaction dashboard that pulls data from MEXC, Bitpanda, and Coinbase exchanges, then presents it in a Vite + React SPA with transaction history, portfolio overview, and P&L/tax reporting. Base currency: EUR. Lives as a new GT rig `crypto-dash`.

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | **Fastify + TypeScript** | Lightweight, built-in schema validation, clean plugin arch |
| Exchange API | **CCXT** | Unified library for 100+ exchanges — handles auth, signing, rate limiting, pagination for all 3 targets |
| Database | **SQLite via better-sqlite3** | Local cache for transactions, fast queries, zero ops |
| Frontend | **Vite + React + TypeScript** | User's choice |
| Tables | **TanStack Table** | Sortable/filterable tables |
| Charts | **Recharts** | Simple React charting for allocation pie + P&L bars |
| Data fetching | **TanStack Query** | Caching, refetch, loading states |
| Styling | **Tailwind CSS** | Fast iteration |
| Monorepo | **npm workspaces** | npm already available, no extra tooling |

## Project Structure

```
crypto-dash/
  package.json                    # Root workspace config
  .env.example / .env (gitignored)
  packages/
    shared/src/
      types.ts                    # Normalized transaction types, exchange enums
    server/src/
      index.ts                    # Fastify entry (port 3001)
      config.ts                   # Env loading, encryption key
      db/
        schema.sql                # SQLite tables
        index.ts                  # DB init + connection
      routes/
        exchanges.ts              # CRUD exchange credentials
        transactions.ts           # Query cached transactions
        balances.ts               # Current balances
        portfolio.ts              # Aggregated portfolio
        pnl.ts                    # P&L calculations
        sync.ts                   # Trigger data refresh
      services/
        exchange-client.ts        # CCXT wrapper
        sync-service.ts           # Fetch + store orchestration
        portfolio-service.ts      # Balance aggregation, EUR conversion
        pnl-service.ts            # FIFO cost basis calculation
    web/src/
      App.tsx                     # Router: /, /transactions, /pnl, /settings
      pages/
        DashboardPage.tsx         # Portfolio overview + allocation chart
        TransactionsPage.tsx      # Filterable transaction table
        PnlPage.tsx               # P&L summary + tax export
        SettingsPage.tsx          # Exchange API key management
      components/
        layout/Shell.tsx, Sidebar.tsx, Header.tsx
        transactions/TransactionTable.tsx, TransactionFilters.tsx
        portfolio/PortfolioOverview.tsx, AllocationChart.tsx, BalanceTable.tsx
        pnl/PnlSummary.tsx, PnlTable.tsx, PnlChart.tsx, TaxExport.tsx
        settings/ExchangeConfig.tsx, SyncStatus.tsx
```

## Data Model (SQLite)

**exchanges** — id, name, api_key (encrypted), api_secret (encrypted), passphrase (encrypted), enabled, last_synced

**transactions** — id (exchange:tx_id), exchange, type (trade/deposit/withdrawal), side (buy/sell), asset, amount, price, quote_currency, total, fee, fee_currency, timestamp, raw_data

**balance_snapshots** — exchange, asset, free, used, total, timestamp

**price_cache** — asset, quote (EUR), price, timestamp

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/exchanges | List exchanges (never returns raw keys) |
| PUT | /api/exchanges/:id | Set exchange credentials |
| POST | /api/sync | Sync all enabled exchanges |
| GET | /api/transactions | Query with filters (exchange, type, asset, dates, sort, pagination) |
| GET | /api/transactions/export | CSV export |
| GET | /api/balances | Current balances |
| GET | /api/portfolio | Aggregated portfolio with EUR values |
| GET | /api/pnl | P&L summary (param: year, method=fifo) |
| GET | /api/pnl/export | Tax CSV export |

## Security

- API keys encrypted at rest (AES-256-GCM, `node:crypto`)
- Encryption master key from `ENCRYPTION_KEY` env var (auto-generated on first run)
- Frontend never sees raw keys (only `hasCredentials: boolean`)
- Users instructed to create **read-only** exchange API keys (no trade/withdraw)
- `.env` gitignored

## P&L Calculation

FIFO (First-In-First-Out) — standard for EU tax reporting:
1. Queue all buy lots per asset chronologically
2. Each sell consumes lots from front of queue
3. Gain = sell proceeds − cost basis of consumed lots
4. Unrealized = remaining lots at current market price
5. Export as CSV for tax filing

## Implementation Phases

### Phase 1: Foundation
- Init monorepo (npm workspaces, tsconfig, .gitignore)
- `packages/shared` with types
- `packages/server`: Fastify setup, SQLite schema, config with encryption
- Exchange credential CRUD routes
- Basic CCXT integration: connect to one exchange, fetch balances
- Verify: store key → fetch balance → return via API

### Phase 2: Data Sync
- `sync-service.ts`: fetch trades, deposits, withdrawals via CCXT
- Normalize + store in SQLite
- Wire up all 3 exchanges (CCXT makes this mostly config)
- `GET /api/transactions` with filtering + pagination
- Incremental sync (store last-fetched timestamp per exchange)

### Phase 3: Frontend Shell
- Vite + React + Tailwind + React Router setup
- App shell (sidebar, header with sync button)
- Settings page (exchange API key forms)
- Transactions page (TanStack Table with sorting/filtering)
- Connect to backend via TanStack Query
- Vite proxy `/api/*` → localhost:3001

### Phase 4: Portfolio Dashboard
- `portfolio-service.ts`: aggregate balances, fetch EUR prices via CCXT
- Dashboard page: total value, allocation pie chart (Recharts), balance table

### Phase 5: P&L & Tax
- `pnl-service.ts` with FIFO calculation
- P&L page: summary cards, per-asset table, monthly gains chart
- CSV export for transactions + P&L

### Phase 6: Polish
- Loading/error/empty states
- Sync progress indicator
- Responsive layout

## Key Dependencies

**Server:** fastify, ccxt, better-sqlite3, dotenv, tsx (dev)
**Web:** react, react-dom, react-router-dom, @tanstack/react-query, @tanstack/react-table, recharts, tailwindcss

## Verification

1. `npm run dev` starts both server (3001) and Vite dev server (5173)
2. Settings page: enter exchange API keys → verify stored (GET /api/exchanges shows hasCredentials: true)
3. Sync: click sync → transactions appear in table
4. Dashboard: portfolio values, allocation chart display correctly
5. P&L: calculations match manual spot-checks against exchange trade history
6. CSV export: downloadable, parseable, matches displayed data

## Beads Task Breakdown

After exiting plan mode, create these beads in HQ (rig doesn't exist yet):

### Epic
- **"Crypto Dashboard Application"** — type=feature, priority=1

### Phase 1: Foundation (depends on nothing)
1. **"Init crypto-dash monorepo with npm workspaces and shared types"** — type=task, P2
2. **"Fastify server setup with SQLite schema and encrypted config"** — type=task, P2, depends on #1
3. **"Exchange credential CRUD API (encrypted storage)"** — type=task, P2, depends on #2

### Phase 2: Data Sync (depends on Phase 1)
4. **"CCXT exchange client wrapper for MEXC, Bitpanda, Coinbase"** — type=task, P2, depends on #3
5. **"Sync service: fetch + normalize + store transactions"** — type=task, P2, depends on #4
6. **"Transaction query API with filtering and pagination"** — type=task, P2, depends on #5

### Phase 3: Frontend Shell (depends on Phase 1)
7. **"Vite + React + Tailwind + Router scaffold"** — type=task, P2, depends on #1
8. **"Settings page: exchange API key management UI"** — type=task, P2, depends on #7, #3
9. **"Transaction history page with TanStack Table"** — type=task, P2, depends on #7, #6

### Phase 4: Portfolio (depends on Phase 2 + 3)
10. **"Portfolio service: balance aggregation + EUR pricing"** — type=task, P2, depends on #5
11. **"Dashboard page: portfolio overview + allocation chart"** — type=task, P2, depends on #7, #10

### Phase 5: P&L (depends on Phase 2 + 3)
12. **"P&L service: FIFO cost basis calculation"** — type=task, P2, depends on #5
13. **"P&L page: summary, per-asset table, tax CSV export"** — type=task, P2, depends on #7, #12

### Phase 6: Polish (depends on everything)
14. **"Polish: loading states, error handling, responsive layout"** — type=task, P3, depends on #9, #11, #13

### Dependency Graph
```
#1 (monorepo init)
├── #2 (server setup) → #3 (credentials API) → #4 (CCXT client) → #5 (sync service)
│                                                                    ├── #6 (tx query API) → #9 (tx page)
│                                                                    ├── #10 (portfolio svc) → #11 (dashboard page)
│                                                                    └── #12 (P&L svc) → #13 (P&L page)
└── #7 (frontend scaffold) → #8 (settings page, also needs #3)
                            → #9, #11, #13 (all pages need scaffold)

#9 + #11 + #13 → #14 (polish)
```

## Notes

- CCXT uses `bitpandapro` for the exchange API. If user has non-Pro Bitpanda (broker), may need a custom adapter later.
- Bitpanda may have limited historical trade API — CSV import could be a fallback.
- All prices normalized to EUR using CCXT ticker data.
