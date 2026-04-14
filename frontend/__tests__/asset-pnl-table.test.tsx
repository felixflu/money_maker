import { render, screen } from '@testing-library/react'
import { AssetPnLTable } from '@/app/components/AssetPnLTable'
import { AssetPnL } from '@/app/types'
import '@testing-library/jest-dom'

const btc: AssetPnL = {
  symbol: 'BTC',
  name: 'Bitcoin',
  costBasis: 50000,
  currentValue: 60000,
  realizedPnL: 2000,
  unrealizedPnL: 8000,
  totalPnL: 10000,
  pnlPercent: 20,
}

const eth: AssetPnL = {
  symbol: 'ETH',
  name: 'Ethereum',
  costBasis: 10000,
  currentValue: 8000,
  realizedPnL: -500,
  unrealizedPnL: -1500,
  totalPnL: -2000,
  pnlPercent: -20,
}

const mockAssets: AssetPnL[] = [btc, eth]

describe('AssetPnLTable', () => {
  describe('empty state', () => {
    it('shows empty message when no assets', () => {
      render(<AssetPnLTable assets={[]} />)
      expect(screen.getByTestId('asset-pnl-empty')).toBeInTheDocument()
      expect(screen.getByText(/no asset p&l data available/i)).toBeInTheDocument()
    })

    it('does not render table when assets empty', () => {
      render(<AssetPnLTable assets={[]} />)
      expect(screen.queryByTestId('asset-pnl-table')).not.toBeInTheDocument()
    })
  })

  describe('renders with data', () => {
    it('renders table container', () => {
      render(<AssetPnLTable assets={mockAssets} />)
      expect(screen.getByTestId('asset-pnl-table')).toBeInTheDocument()
    })

    it('renders a row for each asset', () => {
      render(<AssetPnLTable assets={mockAssets} />)
      expect(screen.getByTestId('asset-pnl-row-BTC')).toBeInTheDocument()
      expect(screen.getByTestId('asset-pnl-row-ETH')).toBeInTheDocument()
    })

    it('renders asset names and symbols', () => {
      render(<AssetPnLTable assets={mockAssets} />)
      expect(screen.getByText('Bitcoin')).toBeInTheDocument()
      expect(screen.getByText('BTC')).toBeInTheDocument()
      expect(screen.getByText('Ethereum')).toBeInTheDocument()
      expect(screen.getByText('ETH')).toBeInTheDocument()
    })

    it('renders column headers', () => {
      render(<AssetPnLTable assets={mockAssets} />)
      expect(screen.getByText('Cost Basis')).toBeInTheDocument()
      expect(screen.getByText('Current Value')).toBeInTheDocument()
      expect(screen.getByText('Realized P&L')).toBeInTheDocument()
      expect(screen.getByText('Unrealized P&L')).toBeInTheDocument()
      expect(screen.getByText('Total P&L')).toBeInTheDocument()
    })
  })

  describe('P&L values', () => {
    it('shows positive total P&L for gaining asset', () => {
      render(<AssetPnLTable assets={[btc]} />)
      const cell = screen.getByTestId('asset-total-pnl-BTC')
      expect(cell.textContent).toContain('+')
      expect(cell).toHaveStyle({ color: '#16a34a' })
    })

    it('shows negative total P&L for losing asset', () => {
      render(<AssetPnLTable assets={[eth]} />)
      const cell = screen.getByTestId('asset-total-pnl-ETH')
      expect(cell).toHaveStyle({ color: '#dc2626' })
    })

    it('displays correct P&L amount for BTC (+$10,000)', () => {
      render(<AssetPnLTable assets={[btc]} />)
      const cell = screen.getByTestId('asset-total-pnl-BTC')
      expect(cell.textContent).toContain('10,000')
    })

    it('displays correct P&L amount for ETH (-$2,000)', () => {
      render(<AssetPnLTable assets={[eth]} />)
      const cell = screen.getByTestId('asset-total-pnl-ETH')
      expect(cell.textContent).toContain('2,000')
    })
  })

  describe('totals row', () => {
    it('renders totals row', () => {
      render(<AssetPnLTable assets={mockAssets} />)
      expect(screen.getByTestId('asset-pnl-total')).toBeInTheDocument()
    })

    it('sums total P&L across all assets', () => {
      // BTC: +10000, ETH: -2000 → net +8000
      render(<AssetPnLTable assets={mockAssets} />)
      const totalCell = screen.getByTestId('asset-pnl-total')
      expect(totalCell.textContent).toContain('8,000')
    })

    it('shows positive color for net positive total', () => {
      render(<AssetPnLTable assets={mockAssets} />)
      const totalCell = screen.getByTestId('asset-pnl-total')
      expect(totalCell).toHaveStyle({ color: '#16a34a' })
    })

    it('shows negative color for net negative total', () => {
      render(<AssetPnLTable assets={[eth]} />)
      const totalCell = screen.getByTestId('asset-pnl-total')
      expect(totalCell).toHaveStyle({ color: '#dc2626' })
    })

    it('displays total with sign prefix', () => {
      render(<AssetPnLTable assets={mockAssets} />)
      const totalCell = screen.getByTestId('asset-pnl-total')
      expect(totalCell.textContent).toContain('+')
    })
  })

  describe('single asset', () => {
    it('renders correctly with one asset', () => {
      render(<AssetPnLTable assets={[btc]} />)
      expect(screen.getByTestId('asset-pnl-table')).toBeInTheDocument()
      expect(screen.getByTestId('asset-pnl-row-BTC')).toBeInTheDocument()
    })
  })
})
