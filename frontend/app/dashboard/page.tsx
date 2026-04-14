'use client'

import { useEffect, useState } from 'react'
import { ProtectedRoute } from '../ProtectedRoute'
import { PortfolioWithPnL } from '../types'
import { PnLChart } from '../components/PnLChart'
import { AssetPnLTable } from '../components/AssetPnLTable'
import { TransactionHistory } from '../components/TransactionHistory'
import { Transaction } from '../types'

async function fetchPortfolio(): Promise<PortfolioWithPnL> {
  await new Promise(resolve => setTimeout(resolve, 500))
  return {
    totalValue: 0,
    holdings: [],
    pnlHistory: [],
    totalPnL: 0,
    totalPnLPercent: 0,
    assetPnL: []
  }
}

async function fetchTransactions(): Promise<Transaction[]> {
  await new Promise(resolve => setTimeout(resolve, 500))
  return []
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
  return `${value.toFixed(2)}%`
}

function DashboardContent() {
  const [portfolio, setPortfolio] = useState<PortfolioWithPnL | null>(null)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadData() {
      try {
        const [portfolioData, transactionData] = await Promise.all([
          fetchPortfolio(),
          fetchTransactions(),
        ])
        setPortfolio(portfolioData)
        setTransactions(transactionData)
      } catch (err) {
        setError('Failed to load portfolio data')
      } finally {
        setIsLoading(false)
      }
    }

    loadData()
  }, [])

  if (isLoading) {
    return (
      <div data-testid="portfolio-loading" style={{ padding: '2rem', textAlign: 'center' }}>
        <p>Loading your portfolio...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div data-testid="portfolio-error" style={{ padding: '2rem', color: 'red' }}>
        <p>{error}</p>
      </div>
    )
  }

  const isEmpty = !portfolio || portfolio.holdings.length === 0

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>Dashboard</h1>

      <div
        data-testid="total-value"
        style={{
          margin: '2rem 0',
          padding: '1.5rem',
          backgroundColor: '#f5f5f5',
          borderRadius: '8px'
        }}
      >
        <h2 style={{ margin: '0 0 0.5rem 0', fontSize: '1rem', color: '#666' }}>
          Total Portfolio Value
        </h2>
        <p style={{ margin: 0, fontSize: '2rem', fontWeight: 'bold' }}>
          {formatCurrency(portfolio?.totalValue || 0)}
        </p>
      </div>

      <section style={{ marginBottom: '2rem' }}>
        <h2>Performance</h2>
        <div
          style={{
            padding: '1.5rem',
            backgroundColor: '#fff',
            borderRadius: '8px',
            border: '1px solid #e5e5e5'
          }}
        >
          <PnLChart
            data={portfolio?.pnlHistory || []}
            initialValue={10000}
          />
        </div>
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2>Asset P&L</h2>
        <div
          style={{
            padding: '1.5rem',
            backgroundColor: '#fff',
            borderRadius: '8px',
            border: '1px solid #e5e5e5',
            overflowX: 'auto'
          }}
        >
          <AssetPnLTable assets={portfolio?.assetPnL || []} />
        </div>
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2>Holdings</h2>

        {isEmpty ? (
          <div
            data-testid="empty-portfolio"
            style={{
              padding: '2rem',
              textAlign: 'center',
              color: '#666',
              backgroundColor: '#fafafa',
              borderRadius: '8px',
              border: '1px dashed #ccc'
            }}
          >
            <p>Your portfolio is empty.</p>
            <p style={{ fontSize: '0.875rem' }}>
              Start adding assets to see your holdings here.
            </p>
          </div>
        ) : (
          <table
            data-testid="holdings-table"
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              marginTop: '1rem'
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem' }}>Asset</th>
                <th style={{ padding: '0.75rem' }}>Symbol</th>
                <th style={{ padding: '0.75rem', textAlign: 'right' }}>Quantity</th>
                <th style={{ padding: '0.75rem', textAlign: 'right' }}>Price</th>
                <th style={{ padding: '0.75rem', textAlign: 'right' }}>Value</th>
                <th style={{ padding: '0.75rem', textAlign: 'right' }}>Allocation</th>
              </tr>
            </thead>
            <tbody>
              {portfolio?.holdings.map((holding) => (
                <tr
                  key={holding.id}
                  data-testid={`holding-row-${holding.symbol}`}
                  style={{ borderBottom: '1px solid #eee' }}
                >
                  <td style={{ padding: '0.75rem' }}>{holding.name}</td>
                  <td style={{ padding: '0.75rem', fontWeight: 'bold' }}>
                    {holding.symbol}
                  </td>
                  <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                    {holding.quantity.toFixed(4)}
                  </td>
                  <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                    {formatCurrency(holding.currentPrice)}
                  </td>
                  <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                    {formatCurrency(holding.value)}
                  </td>
                  <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                    {formatPercentage(
                      portfolio.totalValue > 0
                        ? (holding.value / portfolio.totalValue) * 100
                        : 0
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section
        style={{
          padding: '1.5rem',
          backgroundColor: '#fff',
          borderRadius: '8px',
          border: '1px solid #e5e5e5'
        }}
      >
        <TransactionHistory transactions={transactions} />
      </section>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  )
}
