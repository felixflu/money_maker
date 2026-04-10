'use client'

import { AssetPnL } from '../types'

interface AssetPnLTableProps {
  assets: AssetPnL[]
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function formatPercentage(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

export function AssetPnLTable({ assets }: AssetPnLTableProps) {
  if (assets.length === 0) {
    return (
      <div
        data-testid="asset-pnl-empty"
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: '#666',
          backgroundColor: '#fafafa',
          borderRadius: '8px',
          border: '1px dashed #ccc'
        }}
      >
        <p>No asset P&L data available.</p>
        <p style={{ fontSize: '0.875rem' }}>
          Asset performance will appear once you have holdings.
        </p>
      </div>
    )
  }

  const totalCostBasis = assets.reduce((sum, a) => sum + a.costBasis, 0)
  const totalCurrentValue = assets.reduce((sum, a) => sum + a.currentValue, 0)
  const totalRealizedPnL = assets.reduce((sum, a) => sum + a.realizedPnL, 0)
  const totalUnrealizedPnL = assets.reduce((sum, a) => sum + a.unrealizedPnL, 0)
  const totalPnL = assets.reduce((sum, a) => sum + a.totalPnL, 0)

  return (
    <div data-testid="asset-pnl-table">
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.875rem'
        }}
      >
        <thead>
          <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
            <th style={{ padding: '0.75rem' }}>Asset</th>
            <th style={{ padding: '0.75rem', textAlign: 'right' }}>Cost Basis</th>
            <th style={{ padding: '0.75rem', textAlign: 'right' }}>Current Value</th>
            <th style={{ padding: '0.75rem', textAlign: 'right' }}>Realized P&L</th>
            <th style={{ padding: '0.75rem', textAlign: 'right' }}>Unrealized P&L</th>
            <th style={{ padding: '0.75rem', textAlign: 'right' }}>Total P&L</th>
            <th style={{ padding: '0.75rem', textAlign: 'right' }}>Return %</th>
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => {
            const isPositive = asset.totalPnL >= 0
            const isUnrealizedPositive = asset.unrealizedPnL >= 0
            const isRealizedPositive = asset.realizedPnL >= 0

            return (
              <tr
                key={asset.symbol}
                data-testid={`asset-pnl-row-${asset.symbol}`}
                style={{ borderBottom: '1px solid #eee' }}
              >
                <td style={{ padding: '0.75rem' }}>
                  <div style={{ fontWeight: 500 }}>{asset.name}</div>
                  <div style={{ fontSize: '0.75rem', color: '#666' }}>{asset.symbol}</div>
                </td>
                <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                  {formatCurrency(asset.costBasis)}
                </td>
                <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                  {formatCurrency(asset.currentValue)}
                </td>
                <td
                  style={{
                    padding: '0.75rem',
                    textAlign: 'right',
                    color: asset.realizedPnL === 0 ? '#666' : isRealizedPositive ? '#16a34a' : '#dc2626'
                  }}
                >
                  {formatCurrency(asset.realizedPnL)}
                </td>
                <td
                  style={{
                    padding: '0.75rem',
                    textAlign: 'right',
                    color: asset.unrealizedPnL === 0 ? '#666' : isUnrealizedPositive ? '#16a34a' : '#dc2626'
                  }}
                >
                  {formatCurrency(asset.unrealizedPnL)}
                </td>
                <td
                  data-testid={`asset-total-pnl-${asset.symbol}`}
                  style={{
                    padding: '0.75rem',
                    textAlign: 'right',
                    fontWeight: 500,
                    color: isPositive ? '#16a34a' : '#dc2626'
                  }}
                >
                  {isPositive ? '+' : ''}{formatCurrency(asset.totalPnL)}
                </td>
                <td
                  style={{
                    padding: '0.75rem',
                    textAlign: 'right',
                    color: asset.pnlPercent >= 0 ? '#16a34a' : '#dc2626'
                  }}
                >
                  {formatPercentage(asset.pnlPercent)}
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr style={{ borderTop: '2px solid #ddd', fontWeight: 600 }}>
            <td style={{ padding: '0.75rem' }}>Total</td>
            <td style={{ padding: '0.75rem', textAlign: 'right' }}>
              {formatCurrency(totalCostBasis)}
            </td>
            <td style={{ padding: '0.75rem', textAlign: 'right' }}>
              {formatCurrency(totalCurrentValue)}
            </td>
            <td
              style={{
                padding: '0.75rem',
                textAlign: 'right',
                color: totalRealizedPnL >= 0 ? '#16a34a' : '#dc2626'
              }}
            >
              {totalRealizedPnL >= 0 ? '+' : ''}{formatCurrency(totalRealizedPnL)}
            </td>
            <td
              style={{
                padding: '0.75rem',
                textAlign: 'right',
                color: totalUnrealizedPnL >= 0 ? '#16a34a' : '#dc2626'
              }}
            >
              {totalUnrealizedPnL >= 0 ? '+' : ''}{formatCurrency(totalUnrealizedPnL)}
            </td>
            <td
              data-testid="asset-pnl-total"
              style={{
                padding: '0.75rem',
                textAlign: 'right',
                color: totalPnL >= 0 ? '#16a34a' : '#dc2626'
              }}
            >
              {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)}
            </td>
            <td
              style={{
                padding: '0.75rem',
                textAlign: 'right',
                color: totalCostBasis > 0 && ((totalCurrentValue - totalCostBasis) / totalCostBasis) * 100 >= 0
                  ? '#16a34a'
                  : '#dc2626'
              }}
            >
              {totalCostBasis > 0
                ? formatPercentage(((totalCurrentValue - totalCostBasis) / totalCostBasis) * 100)
                : '0.00%'}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
