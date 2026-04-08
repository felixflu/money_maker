import { render, screen, waitFor } from '@testing-library/react'
import DashboardPage from '@/app/dashboard/page'
import { AuthProvider } from '@/app/AuthContext'
import '@testing-library/jest-dom'

// Mock next/navigation
const mockPush = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

describe('Dashboard', () => {
  beforeEach(() => {
    localStorage.clear()
    mockPush.mockClear()
  })

  describe('Auth-gated routes', () => {
    it('redirects to login when not authenticated', async () => {
      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/login')
      })
    })

    it('shows loading or redirecting state while checking auth', () => {
      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      // Either loading or redirecting state is acceptable during auth check
      const loadingOrRedirecting = screen.queryByTestId('auth-loading') || 
                                   screen.queryByTestId('auth-redirecting')
      expect(loadingOrRedirecting).toBeInTheDocument()
    })

    it('renders dashboard when authenticated', async () => {
      // Mock authenticated state
      localStorage.setItem('mm_auth_tokens', JSON.stringify({
        accessToken: 'mock-token',
        refreshToken: 'mock-refresh'
      }))

      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument()
      })
    })
  })

  describe('Portfolio loading states', () => {
    beforeEach(() => {
      localStorage.setItem('mm_auth_tokens', JSON.stringify({
        accessToken: 'mock-token',
        refreshToken: 'mock-refresh'
      }))
    })

    it('shows portfolio loading state', async () => {
      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      // Wait for auth to complete
      await waitFor(() => {
        expect(screen.queryByTestId('auth-loading')).not.toBeInTheDocument()
      })

      // Should show portfolio loading
      expect(screen.getByTestId('portfolio-loading')).toBeInTheDocument()
    })

    it('shows total portfolio value after loading', async () => {
      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.queryByTestId('portfolio-loading')).not.toBeInTheDocument()
      })

      expect(screen.getByTestId('total-value')).toBeInTheDocument()
    })
  })

  describe('Empty portfolio', () => {
    beforeEach(() => {
      localStorage.setItem('mm_auth_tokens', JSON.stringify({
        accessToken: 'mock-token',
        refreshToken: 'mock-refresh'
      }))
    })

    it('displays empty portfolio message when no holdings', async () => {
      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.queryByTestId('portfolio-loading')).not.toBeInTheDocument()
      })

      expect(screen.getByTestId('empty-portfolio')).toBeInTheDocument()
      expect(screen.getByText(/your portfolio is empty/i)).toBeInTheDocument()
    })

    it('does not show holdings table when empty', async () => {
      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.queryByTestId('portfolio-loading')).not.toBeInTheDocument()
      })

      expect(screen.queryByTestId('holdings-table')).not.toBeInTheDocument()
    })
  })

  describe('Holdings render', () => {
    beforeEach(() => {
      localStorage.setItem('mm_auth_tokens', JSON.stringify({
        accessToken: 'mock-token',
        refreshToken: 'mock-refresh'
      }))
    })

    // This test would pass when we integrate with real API that returns holdings
    // For now with mock empty data, we test the structure exists
    it('renders holdings section header', async () => {
      render(
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.queryByTestId('portfolio-loading')).not.toBeInTheDocument()
      })

      // With empty data, we show holdings heading and empty state
      expect(screen.getByRole('heading', { name: 'Holdings' })).toBeInTheDocument()
    })
  })
})
