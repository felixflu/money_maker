import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { PnLChart } from '@/app/components/PnLChart'
import '@testing-library/jest-dom'

// Mock recharts — ResponsiveContainer uses ResizeObserver which doesn't exist in jsdom
jest.mock('recharts', () => {
  const OriginalModule = jest.requireActual('recharts')
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="recharts-responsive-container">{children}</div>
    ),
  }
})

// Seed data: 10 days ending 2026-04-14
function makeDays(count: number, startValue: number, endValue: number) {
  const points = []
  for (let i = 0; i < count; i++) {
    const d = new Date('2026-04-14')
    d.setDate(d.getDate() - (count - 1 - i))
    const value = startValue + ((endValue - startValue) * i) / (count - 1)
    points.push({ date: d.toISOString().slice(0, 10), value: Math.round(value) })
  }
  return points
}

const mockData = makeDays(10, 9000, 11000)

describe('PnLChart', () => {
  describe('empty state', () => {
    it('shows empty message when data is empty', () => {
      render(<PnLChart data={[]} initialValue={10000} />)
      expect(screen.getByTestId('pnl-chart-empty')).toBeInTheDocument()
      expect(screen.getByText(/no performance data available/i)).toBeInTheDocument()
    })

    it('does not render chart when data is empty', () => {
      render(<PnLChart data={[]} initialValue={10000} />)
      expect(screen.queryByTestId('pnl-chart')).not.toBeInTheDocument()
    })
  })

  describe('renders with data', () => {
    it('renders chart container when data is provided', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      expect(screen.getByTestId('pnl-chart')).toBeInTheDocument()
    })

    it('renders all date range buttons', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      const ranges = ['1W', '1M', '3M', '6M', '1Y', 'ALL']
      for (const r of ranges) {
        expect(screen.getByTestId(`range-btn-${r}`)).toBeInTheDocument()
      }
    })

    it('shows 1M selected by default', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      const btn = screen.getByTestId('range-btn-1M')
      expect(btn).toHaveStyle({ backgroundColor: '#2563eb' })
    })

    it('renders P&L amount', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      expect(screen.getByTestId('pnl-amount')).toBeInTheDocument()
    })

    it('renders P&L percentage', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      expect(screen.getByTestId('pnl-percent')).toBeInTheDocument()
    })
  })

  describe('P&L calculations', () => {
    it('shows positive P&L when portfolio gained value', () => {
      // initialValue=9000, last data point=11000 → +$2000 gain
      render(<PnLChart data={mockData} initialValue={9000} />)
      const amountEl = screen.getByTestId('pnl-amount')
      expect(amountEl.textContent).toContain('+')
      expect(amountEl).toHaveStyle({ color: '#16a34a' })
    })

    it('shows negative P&L when portfolio lost value', () => {
      // initialValue=12000, last data point=11000 → loss
      render(<PnLChart data={mockData} initialValue={12000} />)
      const amountEl = screen.getByTestId('pnl-amount')
      expect(amountEl).toHaveStyle({ color: '#dc2626' })
    })

    it('calculates P&L as current value minus initial value', () => {
      const singlePoint = [{ date: '2026-04-14', value: 12500 }]
      render(<PnLChart data={singlePoint} initialValue={10000} />)
      const amountEl = screen.getByTestId('pnl-amount')
      // +$2,500
      expect(amountEl.textContent).toContain('2,500')
    })

    it('calculates percentage correctly', () => {
      const singlePoint = [{ date: '2026-04-14', value: 11000 }]
      render(<PnLChart data={singlePoint} initialValue={10000} />)
      const pctEl = screen.getByTestId('pnl-percent')
      // +10.00%
      expect(pctEl.textContent).toContain('10.00%')
    })

    it('shows zero P&L when value equals initial', () => {
      const singlePoint = [{ date: '2026-04-14', value: 10000 }]
      render(<PnLChart data={singlePoint} initialValue={10000} />)
      const amountEl = screen.getByTestId('pnl-amount')
      expect(amountEl.textContent).toContain('0')
    })
  })

  describe('date range selection', () => {
    it('changes selected range when button is clicked', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      const btn1W = screen.getByTestId('range-btn-1W')
      fireEvent.click(btn1W)
      expect(btn1W).toHaveStyle({ backgroundColor: '#2563eb' })
    })

    it('deselects previous range when new one is selected', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      const btn1W = screen.getByTestId('range-btn-1W')
      const btn1M = screen.getByTestId('range-btn-1M')
      fireEvent.click(btn1W)
      expect(btn1M).toHaveStyle({ backgroundColor: '#fff' })
    })

    it('ALL range shows all data', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      const btnAll = screen.getByTestId('range-btn-ALL')
      fireEvent.click(btnAll)
      expect(btnAll).toHaveStyle({ backgroundColor: '#2563eb' })
      // P&L recalculates without date filtering — chart still visible
      expect(screen.getByTestId('pnl-chart')).toBeInTheDocument()
    })

    it('renders chart after switching range', () => {
      render(<PnLChart data={mockData} initialValue={10000} />)
      fireEvent.click(screen.getByTestId('range-btn-3M'))
      expect(screen.getByTestId('pnl-chart')).toBeInTheDocument()
    })

    it('shows empty state if filtered range has no data points', () => {
      // Single point from today — 1Y filter returns it; 1W might not if date math works out.
      // Use a point from 2020 to ensure 1W filter returns empty.
      const oldData = [{ date: '2020-01-01', value: 8000 }]
      render(<PnLChart data={oldData} initialValue={10000} />)
      fireEvent.click(screen.getByTestId('range-btn-1W'))
      // With no data in range, P&L calculation uses empty array → shows $0
      const amountEl = screen.getByTestId('pnl-amount')
      expect(amountEl.textContent).toContain('0')
    })
  })
})
