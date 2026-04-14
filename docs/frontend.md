# Frontend Documentation

## Charting

### Library: Recharts

Portfolio charts use [Recharts](https://recharts.org/) (`recharts` ^3.x).

Chosen for: React-native API, composable primitives, TypeScript types, good jsdom test compatibility via module mocking.

### Components

#### `PnLChart` (`app/components/PnLChart.tsx`)

Line chart showing portfolio value over time with P&L overlay.

**Props:**
```ts
interface PnLChartProps {
  data: PnLDataPoint[]   // { date: string (ISO), value: number }
  initialValue?: number  // cost basis / starting value for P&L calculation
}
```

**Data flow:**
1. Dashboard fetches `PortfolioWithPnL` which includes `pnlHistory: PnLDataPoint[]`
2. `PnLChart` receives `pnlHistory` and `initialValue` (total cost basis)
3. Client-side date filtering narrows data to selected range (1W/1M/3M/6M/1Y/ALL)
4. P&L = `filteredData[last].value - initialValue`
5. Percentage = `(P&L / initialValue) * 100`

**Empty state:** Shown when `data.length === 0`. Displays `data-testid="pnl-chart-empty"`.

**Date ranges:** Default is `1M`. Switching range re-filters client-side — no network request.

#### `AssetPnLTable` (`app/components/AssetPnLTable.tsx`)

Table of per-asset P&L breakdown: cost basis, current value, realized/unrealized/total P&L, return %.

**Props:**
```ts
interface AssetPnLTableProps {
  assets: AssetPnL[]
}
```

**P&L calculation methodology:**
- `realizedPnL`: gains/losses from closed positions (sells)
- `unrealizedPnL`: open position gain/loss = `currentValue - costBasis - realizedPnL`
- `totalPnL`: `realizedPnL + unrealizedPnL`
- `pnlPercent`: `(totalPnL / costBasis) * 100`

Totals row aggregates cost basis, current value, realized, unrealized, and total P&L across all assets.

**Empty state:** Shown when `assets.length === 0`. Displays `data-testid="asset-pnl-empty"`.

### Testing Charts

Recharts uses `ResizeObserver` internally. Mock `ResponsiveContainer` in jsdom tests:

```ts
jest.mock('recharts', () => {
  const OriginalModule = jest.requireActual('recharts')
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div>{children}</div>
    ),
  }
})
```

Test files: `__tests__/pnl-chart.test.tsx`, `__tests__/asset-pnl-table.test.tsx`

Coverage areas: render with data, empty state, date range selection, P&L calculations, totals.
