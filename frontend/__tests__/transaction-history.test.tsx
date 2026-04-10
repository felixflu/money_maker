import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { TransactionHistory } from '@/app/components/TransactionHistory'
import '@testing-library/jest-dom'

// Mock transactions data
const mockTransactions = [
  {
    id: 'tx-1',
    exchange: 'Coinbase',
    asset: 'Bitcoin',
    symbol: 'BTC',
    type: 'buy' as const,
    quantity: 0.5,
    price: 50000,
    total: 25000,
    timestamp: '2026-04-01T10:00:00Z',
    status: 'completed' as const,
  },
  {
    id: 'tx-2',
    exchange: 'Binance',
    asset: 'Ethereum',
    symbol: 'ETH',
    type: 'sell' as const,
    quantity: 2,
    price: 3000,
    total: 6000,
    timestamp: '2026-04-05T14:30:00Z',
    status: 'completed' as const,
  },
  {
    id: 'tx-3',
    exchange: 'Coinbase',
    asset: 'Solana',
    symbol: 'SOL',
    type: 'buy' as const,
    quantity: 10,
    price: 150,
    total: 1500,
    timestamp: '2026-04-08T09:15:00Z',
    status: 'pending' as const,
  },
  {
    id: 'tx-4',
    exchange: 'Kraken',
    asset: 'Bitcoin',
    symbol: 'BTC',
    type: 'transfer' as const,
    quantity: 0.1,
    price: 51000,
    total: 5100,
    timestamp: '2026-04-09T16:45:00Z',
    status: 'completed' as const,
  },
  {
    id: 'tx-5',
    exchange: 'Binance',
    asset: 'Cardano',
    symbol: 'ADA',
    type: 'buy' as const,
    quantity: 1000,
    price: 0.5,
    total: 500,
    timestamp: '2026-04-09T11:20:00Z',
    status: 'failed' as const,
  },
]

describe('TransactionHistory', () => {
  beforeEach(() => {
    // Mock URL.createObjectURL and revokeObjectURL
    global.URL.createObjectURL = jest.fn(() => 'mock-url')
    global.URL.revokeObjectURL = jest.fn()
  })

  describe('Table rendering', () => {
    it('renders transaction table with headers', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      expect(screen.getByRole('heading', { name: /transaction history/i })).toBeInTheDocument()
      expect(screen.getByTestId('transactions-table')).toBeInTheDocument()

      // Check table headers
      expect(screen.getByRole('columnheader', { name: /exchange/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /asset/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /type/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /quantity/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /price/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /total/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /date/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /status/i })).toBeInTheDocument()
    })

    it('renders transaction rows correctly', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      expect(screen.getByText('Coinbase')).toBeInTheDocument()
      expect(screen.getByText('Bitcoin')).toBeInTheDocument()
      expect(screen.getByText('BTC')).toBeInTheDocument()
      expect(screen.getByText('Binance')).toBeInTheDocument()
      expect(screen.getByText('Ethereum')).toBeInTheDocument()
    })

    it('displays correct number of rows based on page size', () => {
      render(<TransactionHistory transactions={mockTransactions} pageSize={2} />)

      const rows = screen.getAllByRole('row').filter(row => row.querySelector('td'))
      expect(rows).toHaveLength(2)
    })
  })

  describe('Pagination', () => {
    it('shows pagination controls when transactions exceed page size', () => {
      render(<TransactionHistory transactions={mockTransactions} pageSize={2} />)

      expect(screen.getByTestId('pagination-controls')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
    })

    it('shows page indicator with current page and total pages', () => {
      render(<TransactionHistory transactions={mockTransactions} pageSize={2} />)

      expect(screen.getByTestId('page-indicator')).toHaveTextContent('Page 1 of 3')
    })

    it('navigates to next page when clicking next', () => {
      render(<TransactionHistory transactions={mockTransactions} pageSize={2} />)

      const nextButton = screen.getByRole('button', { name: /next/i })
      fireEvent.click(nextButton)

      expect(screen.getByTestId('page-indicator')).toHaveTextContent('Page 2 of 3')
    })

    it('navigates to previous page when clicking previous', () => {
      render(<TransactionHistory transactions={mockTransactions} pageSize={2} />)

      const nextButton = screen.getByRole('button', { name: /next/i })
      fireEvent.click(nextButton)
      fireEvent.click(nextButton)

      const prevButton = screen.getByRole('button', { name: /previous/i })
      fireEvent.click(prevButton)

      expect(screen.getByTestId('page-indicator')).toHaveTextContent('Page 2 of 3')
    })

    it('disables previous button on first page', () => {
      render(<TransactionHistory transactions={mockTransactions} pageSize={2} />)

      const prevButton = screen.getByRole('button', { name: /previous/i })
      expect(prevButton).toBeDisabled()
    })

    it('disables next button on last page', () => {
      render(<TransactionHistory transactions={mockTransactions} pageSize={2} />)

      const nextButton = screen.getByRole('button', { name: /next/i })
      fireEvent.click(nextButton)
      fireEvent.click(nextButton)

      expect(nextButton).toBeDisabled()
    })
  })

  describe('Filters', () => {
    it('renders filter controls', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      expect(screen.getByTestId('filter-controls')).toBeInTheDocument()
      expect(screen.getByRole('combobox', { name: /exchange/i })).toBeInTheDocument()
      expect(screen.getByRole('combobox', { name: /asset/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/from date/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/to date/i)).toBeInTheDocument()
    })

    it('filters by exchange', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      const exchangeFilter = screen.getByRole('combobox', { name: /exchange/i })
      fireEvent.change(exchangeFilter, { target: { value: 'Coinbase' } })

      const rows = screen.getAllByRole('row').filter(row => row.querySelector('td'))
      expect(rows).toHaveLength(2)
      expect(screen.getAllByText('Coinbase')).toHaveLength(2)
    })

    it('filters by asset', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      const assetFilter = screen.getByRole('combobox', { name: /asset/i })
      fireEvent.change(assetFilter, { target: { value: 'Bitcoin' } })

      const rows = screen.getAllByRole('row').filter(row => row.querySelector('td'))
      expect(rows).toHaveLength(2)
    })

    it('filters by date range', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      const fromDate = screen.getByLabelText(/from date/i)
      const toDate = screen.getByLabelText(/to date/i)

      fireEvent.change(fromDate, { target: { value: '2026-04-05' } })
      fireEvent.change(toDate, { target: { value: '2026-04-08' } })

      const rows = screen.getAllByRole('row').filter(row => row.querySelector('td'))
      // Should show only the transaction from April 5 and April 8
      expect(rows.length).toBeGreaterThanOrEqual(1)
      expect(rows.length).toBeLessThan(mockTransactions.length)
    })

    it('clears filters when clicking clear button', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      const exchangeFilter = screen.getByRole('combobox', { name: /exchange/i })
      fireEvent.change(exchangeFilter, { target: { value: 'Coinbase' } })

      const clearButton = screen.getByRole('button', { name: /clear filters/i })
      fireEvent.click(clearButton)

      expect(exchangeFilter).toHaveValue('')
    })
  })

  describe('CSV Export', () => {
    it('renders export button', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument()
    })

    it('exports filtered transactions to CSV', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      const exchangeFilter = screen.getByRole('combobox', { name: /exchange/i })
      fireEvent.change(exchangeFilter, { target: { value: 'Coinbase' } })

      const exportButton = screen.getByRole('button', { name: /export csv/i })
      fireEvent.click(exportButton)

      expect(global.URL.createObjectURL).toHaveBeenCalled()
    })

    it('exports all transactions when no filters applied', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      const exportButton = screen.getByRole('button', { name: /export csv/i })
      fireEvent.click(exportButton)

      expect(global.URL.createObjectURL).toHaveBeenCalled()
    })
  })

  describe('Empty state', () => {
    it('shows empty state when no transactions provided', () => {
      render(<TransactionHistory transactions={[]} />)

      expect(screen.getByTestId('empty-transactions')).toBeInTheDocument()
      expect(screen.getByText(/no transactions found/i)).toBeInTheDocument()
    })

    it('shows empty state when filters match no transactions', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      const exchangeFilter = screen.getByRole('combobox', { name: /exchange/i })
      fireEvent.change(exchangeFilter, { target: { value: 'NonExistentExchange' } })

      expect(screen.getByTestId('empty-transactions')).toBeInTheDocument()
    })

    it('does not show table when transactions are empty', () => {
      render(<TransactionHistory transactions={[]} />)

      expect(screen.queryByTestId('transactions-table')).not.toBeInTheDocument()
    })

    it('does not show pagination when transactions are empty', () => {
      render(<TransactionHistory transactions={[]} />)

      expect(screen.queryByTestId('pagination-controls')).not.toBeInTheDocument()
    })
  })

  describe('Transaction formatting', () => {
    it('formats currency values correctly', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      // Check for formatted prices (e.g., $50,000.00)
      expect(screen.getByText('$50,000.00')).toBeInTheDocument()
      expect(screen.getByText('$25,000.00')).toBeInTheDocument()
    })

    it('formats dates correctly', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      // Check for formatted dates
      expect(screen.getByText(/2026/)).toBeInTheDocument()
    })

    it('displays transaction types with proper styling', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      expect(screen.getByText('buy')).toBeInTheDocument()
      expect(screen.getByText('sell')).toBeInTheDocument()
      expect(screen.getByText('transfer')).toBeInTheDocument()
    })

    it('displays status with proper styling', () => {
      render(<TransactionHistory transactions={mockTransactions} />)

      expect(screen.getByText('completed')).toBeInTheDocument()
      expect(screen.getByText('pending')).toBeInTheDocument()
      expect(screen.getByText('failed')).toBeInTheDocument()
    })
  })
})
