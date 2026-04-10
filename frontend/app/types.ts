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

export interface Transaction {
  id: string
  exchange: string
  asset: string
  symbol: string
  type: 'buy' | 'sell' | 'transfer' | 'deposit' | 'withdrawal'
  quantity: number
  price: number
  total: number
  timestamp: string
  status: 'completed' | 'pending' | 'failed'
}

export interface TransactionFilters {
  exchange?: string
  asset?: string
  dateFrom?: string
  dateTo?: string
  type?: Transaction['type']
  status?: Transaction['status']
}

export interface AuthUser {
  id: string
  email: string
}

export interface AuthTokens {
  accessToken: string
  refreshToken: string
}
