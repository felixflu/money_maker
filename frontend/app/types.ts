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
