'use client'

import { useState, useMemo } from 'react'
import { Transaction, TransactionFilters } from '../types'

interface TransactionHistoryProps {
  transactions: Transaction[]
  pageSize?: number
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function formatDate(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function exportToCSV(transactions: Transaction[]): void {
  const headers = ['Exchange', 'Asset', 'Symbol', 'Type', 'Quantity', 'Price', 'Total', 'Date', 'Status']
  const rows = transactions.map(tx => [
    tx.exchange,
    tx.asset,
    tx.symbol,
    tx.type,
    tx.quantity.toString(),
    tx.price.toString(),
    tx.total.toString(),
    tx.timestamp,
    tx.status,
  ])

  const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `transactions_${new Date().toISOString().split('T')[0]}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function TransactionHistory({ transactions, pageSize = 10 }: TransactionHistoryProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [filters, setFilters] = useState<TransactionFilters>({})

  // Get unique values for filter dropdowns
  const exchanges = useMemo(() => {
    const unique = new Set(transactions.map(tx => tx.exchange))
    return Array.from(unique).sort()
  }, [transactions])

  const assets = useMemo(() => {
    const unique = new Set(transactions.map(tx => tx.asset))
    return Array.from(unique).sort()
  }, [transactions])

  // Apply filters
  const filteredTransactions = useMemo(() => {
    return transactions.filter(tx => {
      if (filters.exchange && tx.exchange !== filters.exchange) return false
      if (filters.asset && tx.asset !== filters.asset) return false
      if (filters.dateFrom && new Date(tx.timestamp) < new Date(filters.dateFrom)) return false
      if (filters.dateTo && new Date(tx.timestamp) > new Date(filters.dateTo + 'T23:59:59')) return false
      if (filters.type && tx.type !== filters.type) return false
      if (filters.status && tx.status !== filters.status) return false
      return true
    })
  }, [transactions, filters])

  // Pagination
  const totalPages = Math.ceil(filteredTransactions.length / pageSize)
  const paginatedTransactions = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredTransactions.slice(start, start + pageSize)
  }, [filteredTransactions, currentPage, pageSize])

  const handleFilterChange = (key: keyof TransactionFilters, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value || undefined }))
    setCurrentPage(1) // Reset to first page when filter changes
  }

  const clearFilters = () => {
    setFilters({})
    setCurrentPage(1)
  }

  const handleExport = () => {
    exportToCSV(filteredTransactions)
  }

  const hasActiveFilters = Object.values(filters).some(v => v !== undefined && v !== '')

  if (transactions.length === 0) {
    return (
      <div
        data-testid="empty-transactions"
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: '#666',
          backgroundColor: '#fafafa',
          borderRadius: '8px',
          border: '1px dashed #ccc',
        }}
      >
        <p>No transactions found.</p>
        <p style={{ fontSize: '0.875rem' }}>
          Transactions will appear here once they are available.
        </p>
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Transaction History</h2>
        <button
          onClick={handleExport}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Export CSV
        </button>
      </div>

      {/* Filter Controls */}
      <div data-testid="filter-controls" style={{ marginBottom: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <label htmlFor="exchange-filter" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>
            Exchange
          </label>
          <select
            id="exchange-filter"
            aria-label="Exchange"
            value={filters.exchange || ''}
            onChange={e => handleFilterChange('exchange', e.target.value)}
            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc' }}
          >
            <option value="">All</option>
            {exchanges.map(exchange => (
              <option key={exchange} value={exchange}>
                {exchange}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="asset-filter" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>
            Asset
          </label>
          <select
            id="asset-filter"
            aria-label="Asset"
            value={filters.asset || ''}
            onChange={e => handleFilterChange('asset', e.target.value)}
            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc' }}
          >
            <option value="">All</option>
            {assets.map(asset => (
              <option key={asset} value={asset}>
                {asset}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="from-date" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>
            From Date
          </label>
          <input
            id="from-date"
            type="date"
            aria-label="From Date"
            value={filters.dateFrom || ''}
            onChange={e => handleFilterChange('dateFrom', e.target.value)}
            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc' }}
          />
        </div>

        <div>
          <label htmlFor="to-date" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>
            To Date
          </label>
          <input
            id="to-date"
            type="date"
            aria-label="To Date"
            value={filters.dateTo || ''}
            onChange={e => handleFilterChange('dateTo', e.target.value)}
            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc' }}
          />
        </div>

        {hasActiveFilters && (
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <button
              onClick={clearFilters}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#6c757d',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>

      {/* Results count */}
      <div style={{ marginBottom: '1rem', fontSize: '0.875rem', color: '#666' }}>
        Showing {filteredTransactions.length} transaction{filteredTransactions.length !== 1 ? 's' : ''}
      </div>

      {/* Transaction Table */}
      {filteredTransactions.length === 0 ? (
        <div
          data-testid="empty-transactions"
          style={{
            padding: '2rem',
            textAlign: 'center',
            color: '#666',
            backgroundColor: '#fafafa',
            borderRadius: '8px',
            border: '1px dashed #ccc',
          }}
        >
          <p>No transactions found matching your filters.</p>
          <p style={{ fontSize: '0.875rem' }}>Try adjusting your filter criteria.</p>
        </div>
      ) : (
        <table
          data-testid="transactions-table"
          style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem' }}
        >
          <thead>
            <tr style={{ borderBottom: '2px solid #ddd', textAlign: 'left' }}>
              <th style={{ padding: '0.75rem' }}>Exchange</th>
              <th style={{ padding: '0.75rem' }}>Asset</th>
              <th style={{ padding: '0.75rem' }}>Type</th>
              <th style={{ padding: '0.75rem', textAlign: 'right' }}>Quantity</th>
              <th style={{ padding: '0.75rem', textAlign: 'right' }}>Price</th>
              <th style={{ padding: '0.75rem', textAlign: 'right' }}>Total</th>
              <th style={{ padding: '0.75rem' }}>Date</th>
              <th style={{ padding: '0.75rem' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {paginatedTransactions.map(tx => (
              <tr key={tx.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '0.75rem' }}>{tx.exchange}</td>
                <td style={{ padding: '0.75rem' }}>
                  {tx.asset}
                  <span style={{ fontSize: '0.75rem', color: '#666', marginLeft: '0.5rem' }}>
                    ({tx.symbol})
                  </span>
                </td>
                <td style={{ padding: '0.75rem' }}>
                  <span
                    style={{
                      textTransform: 'capitalize',
                      padding: '0.25rem 0.5rem',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 500,
                      backgroundColor:
                        tx.type === 'buy'
                          ? '#d4edda'
                          : tx.type === 'sell'
                            ? '#f8d7da'
                            : '#e2e3e5',
                      color:
                        tx.type === 'buy'
                          ? '#155724'
                          : tx.type === 'sell'
                            ? '#721c24'
                            : '#383d41',
                    }}
                  >
                    {tx.type}
                  </span>
                </td>
                <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                  {tx.quantity.toLocaleString()}
                </td>
                <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                  {formatCurrency(tx.price)}
                </td>
                <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                  {formatCurrency(tx.total)}
                </td>
                <td style={{ padding: '0.75rem', fontSize: '0.875rem' }}>
                  {formatDate(tx.timestamp)}
                </td>
                <td style={{ padding: '0.75rem' }}>
                  <span
                    style={{
                      textTransform: 'capitalize',
                      padding: '0.25rem 0.5rem',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 500,
                      backgroundColor:
                        tx.status === 'completed'
                          ? '#d4edda'
                          : tx.status === 'pending'
                            ? '#fff3cd'
                            : '#f8d7da',
                      color:
                        tx.status === 'completed'
                          ? '#155724'
                          : tx.status === 'pending'
                            ? '#856404'
                            : '#721c24',
                    }}
                  >
                    {tx.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Pagination */}
      {filteredTransactions.length > 0 && totalPages > 1 && (
        <div
          data-testid="pagination-controls"
          style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem' }}
        >
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: currentPage === 1 ? '#e9ecef' : '#007bff',
              color: currentPage === 1 ? '#6c757d' : 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
            }}
          >
            Previous
          </button>
          <span data-testid="page-indicator">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: currentPage === totalPages ? '#e9ecef' : '#007bff',
              color: currentPage === totalPages ? '#6c757d' : 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
            }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
