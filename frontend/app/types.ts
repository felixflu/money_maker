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

export interface SupportedExchange {
  name: string
  display_name: string
  description: string
  supported_features: string[]
  requires_api_secret: boolean
  website_url: string | null
  docs_url: string | null
}

export interface ExchangeConnection {
  id: number
  user_id: number
  exchange_name: string
  is_active: boolean
  additional_config: string | null
  last_synced_at: string | null
  created_at: string
  updated_at: string
  api_key_masked: string | null
}

export interface BankConnectionInitiation {
  id: string
  web_form_url: string
  process_id: string
}

export interface BankAccount {
  id: string
  name: string
  iban: string
  balance: number
}

export interface BankSyncStatus {
  status: 'RUNNING' | 'COMPLETED' | 'FAILED'
  progress?: number
  bank_connection_id?: string
  accounts?: BankAccount[]
  error?: string
}

// Exchanges that use WealthAPI bank redirect flow instead of API key/secret
export const WEALTHAPI_REDIRECT_EXCHANGES = new Set(['trade_republic'])

export interface PortfolioWithPnL extends Portfolio {
  pnlHistory: PnLDataPoint[]
  totalPnL: number
  totalPnLPercent: number
  assetPnL: AssetPnL[]
}
