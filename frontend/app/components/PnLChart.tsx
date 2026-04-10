'use client'

import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts'
import { PnLDataPoint } from '../types'

type DateRange = '1W' | '1M' | '3M' | '6M' | '1Y' | 'ALL'

interface PnLChartProps {
  data: PnLDataPoint[]
  initialValue?: number
}

const rangeLabels: Record<DateRange, string> = {
  '1W': '1 Week',
  '1M': '1 Month',
  '3M': '3 Months',
  '6M': '6 Months',
  '1Y': '1 Year',
  'ALL': 'All Time'
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function formatDate(dateStr: string, range: DateRange): string {
  const date = new Date(dateStr)
  if (range === '1W' || range === '1M') {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
  return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

function filterDataByRange(data: PnLDataPoint[], range: DateRange): PnLDataPoint[] {
  if (range === 'ALL' || data.length === 0) return data

  const now = new Date()
  const cutoff = new Date()

  switch (range) {
    case '1W':
      cutoff.setDate(now.getDate() - 7)
      break
    case '1M':
      cutoff.setMonth(now.getMonth() - 1)
      break
    case '3M':
      cutoff.setMonth(now.getMonth() - 3)
      break
    case '6M':
      cutoff.setMonth(now.getMonth() - 6)
      break
    case '1Y':
      cutoff.setFullYear(now.getFullYear() - 1)
      break
  }

  return data.filter(d => new Date(d.date) >= cutoff)
}

function calculatePnL(data: PnLDataPoint[], initialValue: number): { totalPnL: number; percent: number } {
  if (data.length === 0) return { totalPnL: 0, percent: 0 }
  const currentValue = data[data.length - 1].value
  const totalPnL = currentValue - initialValue
  const percent = initialValue > 0 ? (totalPnL / initialValue) * 100 : 0
  return { totalPnL, percent }
}

export function PnLChart({ data, initialValue = 0 }: PnLChartProps) {
  const [selectedRange, setSelectedRange] = useState<DateRange>('1M')
  const filteredData = filterDataByRange(data, selectedRange)
  const { totalPnL, percent } = calculatePnL(filteredData, initialValue)
  const isPositive = totalPnL >= 0

  if (data.length === 0) {
    return (
      <div
        data-testid="pnl-chart-empty"
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: '#666',
          backgroundColor: '#fafafa',
          borderRadius: '8px',
          border: '1px dashed #ccc'
        }}
      >
        <p>No performance data available.</p>
        <p style={{ fontSize: '0.875rem' }}>
          Portfolio history will appear once you have holdings.
        </p>
      </div>
    )
  }

  return (
    <div data-testid="pnl-chart">
      <div style={{ marginBottom: '1.5rem' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem'
          }}
        >
          <div>
            <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '0.875rem', color: '#666' }}>
              P&L ({rangeLabels[selectedRange]})
            </h3>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem' }}>
              <span
                data-testid="pnl-amount"
                style={{
                  fontSize: '1.5rem',
                  fontWeight: 'bold',
                  color: isPositive ? '#16a34a' : '#dc2626'
                }}
              >
                {isPositive ? '+' : ''}{formatCurrency(totalPnL)}
              </span>
              <span
                data-testid="pnl-percent"
                style={{
                  fontSize: '1rem',
                  color: isPositive ? '#16a34a' : '#dc2626'
                }}
              >
                ({isPositive ? '+' : ''}{percent.toFixed(2)}%)
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.25rem' }}>
            {(Object.keys(rangeLabels) as DateRange[]).map(range => (
              <button
                key={range}
                data-testid={`range-btn-${range}`}
                onClick={() => setSelectedRange(range)}
                style={{
                  padding: '0.375rem 0.75rem',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  backgroundColor: selectedRange === range ? '#2563eb' : '#fff',
                  color: selectedRange === range ? '#fff' : '#333',
                  fontSize: '0.75rem',
                  fontWeight: 500,
                  cursor: 'pointer'
                }}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={filteredData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis
              dataKey="date"
              tickFormatter={(date) => formatDate(date, selectedRange)}
              tick={{ fontSize: 12 }}
              stroke="#999"
            />
            <YAxis
              tickFormatter={(value) => formatCurrency(value)}
              tick={{ fontSize: 12 }}
              stroke="#999"
              width={70}
            />
            <Tooltip
              formatter={(value: number) => [formatCurrency(value), 'Value']}
              labelFormatter={(label) => new Date(label).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
              })}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #ddd',
                borderRadius: '4px'
              }}
            />
            <ReferenceLine y={initialValue} stroke="#999" strokeDasharray="3 3" />
            <Line
              type="monotone"
              dataKey="value"
              stroke={isPositive ? '#16a34a' : '#dc2626'}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              data-testid="pnl-line"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
