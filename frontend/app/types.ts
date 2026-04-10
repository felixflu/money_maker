export interface Holding {
  id: string
  symbol: string
  name: string
  quantity: number
  currentPrice: number
  value: number
}

export interface Portfolio {
  totalValue: number
  holdings: Holding[]
}

export interface AuthUser {
  id: string
  email: string
}

export interface AuthTokens {
  accessToken: string
  refreshToken: string
}

export interface PnLDataPoint {
  date: string
  value: number
}

export interface AssetPnL {
  symbol: string
  name: string
  costBasis: number
  currentValue: number
  realizedPnL: number
  unrealizedPnL: number
  totalPnL: number
  pnlPercent: number
}

export interface PortfolioWithPnL extends Portfolio {
  pnlHistory: PnLDataPoint[]
  totalPnL: number
  totalPnLPercent: number
  assetPnL: AssetPnL[]
}
