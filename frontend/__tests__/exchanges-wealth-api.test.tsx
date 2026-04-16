import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ExchangeConnectionsPage from '@/app/exchanges/page'
import WealthApiCallbackPage from '@/app/exchanges/callback/page'
import { AuthProvider } from '@/app/AuthContext'
import '@testing-library/jest-dom'

const mockPush = jest.fn()
const mockSearchParams = new URLSearchParams()

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => mockSearchParams,
}))

const MOCK_EXCHANGES = {
  exchanges: [
    {
      name: 'trade_republic',
      display_name: 'Trade Republic',
      description: 'German neobroker',
      supported_features: ['portfolio_sync'],
      requires_api_secret: true,
      website_url: null,
      docs_url: null,
    },
    {
      name: 'coinbase',
      display_name: 'Coinbase',
      description: 'Crypto exchange',
      supported_features: ['portfolio_sync'],
      requires_api_secret: true,
      website_url: null,
      docs_url: null,
    },
  ],
}

function setAuthenticated() {
  localStorage.setItem(
    'mm_auth_tokens',
    JSON.stringify({ accessToken: 'mock-token', refreshToken: 'mock-refresh' })
  )
}

function mockFetchResponses(responses: Array<{ ok: boolean; data: unknown; status?: number }>) {
  let callIndex = 0
  global.fetch = jest.fn((() => {
    const resp = responses[callIndex] || responses[responses.length - 1]
    callIndex++
    return Promise.resolve({
      ok: resp.ok,
      status: resp.status || (resp.ok ? 200 : 500),
      json: async () => resp.data,
    })
  }) as jest.Mock) as jest.Mock
}

beforeEach(() => {
  localStorage.clear()
  mockPush.mockClear()
})

afterEach(() => {
  jest.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Trade Republic uses WealthAPI redirect flow (not API key/secret)
// ---------------------------------------------------------------------------

describe('WealthAPI Bank Connection Flow', () => {
  describe('Add Connection Form — Trade Republic redirect', () => {
    it('shows "Connect via Bank" button instead of API key fields for Trade Republic', async () => {
      setAuthenticated()
      mockFetchResponses([
        { ok: true, data: MOCK_EXCHANGES },
        { ok: true, data: [] }, // no existing connections
      ])

      render(
        <AuthProvider>
          <ExchangeConnectionsPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('add-connection-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('add-connection-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('add-connection-form')).toBeInTheDocument()
      })

      // Trade Republic should be selected by default (first available)
      // Should show bank connect button, NOT API key inputs
      expect(screen.getByTestId('bank-connect-btn')).toBeInTheDocument()
      expect(screen.queryByTestId('api-key-input')).not.toBeInTheDocument()
    })

    it('shows API key fields when non-redirect exchange selected', async () => {
      setAuthenticated()
      mockFetchResponses([
        { ok: true, data: MOCK_EXCHANGES },
        { ok: true, data: [] },
      ])

      render(
        <AuthProvider>
          <ExchangeConnectionsPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('add-connection-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('add-connection-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('exchange-select')).toBeInTheDocument()
      })

      // Select Coinbase (uses API key flow)
      await userEvent.selectOptions(screen.getByTestId('exchange-select'), 'coinbase')

      expect(screen.getByTestId('api-key-input')).toBeInTheDocument()
      expect(screen.queryByTestId('bank-connect-btn')).not.toBeInTheDocument()
    })

    it('calls initiate bank connection API and redirects on click', async () => {
      setAuthenticated()
      mockFetchResponses([
        { ok: true, data: MOCK_EXCHANGES },
        { ok: true, data: [] },
        // Initiate bank connection response
        {
          ok: true,
          data: {
            id: 'bc-123',
            web_form_url: 'https://sandbox.wealthapi.eu/webform/abc123',
            process_id: 'proc-456',
          },
        },
      ])

      // Mock window.location.assign
      const assignMock = jest.fn()
      Object.defineProperty(window, 'location', {
        value: { ...window.location, assign: assignMock },
        writable: true,
      })

      render(
        <AuthProvider>
          <ExchangeConnectionsPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('add-connection-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('add-connection-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('bank-connect-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('bank-connect-btn'))

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/wealthapi/bank-connections',
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('trade_republic'),
          })
        )
      })

      await waitFor(() => {
        expect(assignMock).toHaveBeenCalledWith(
          'https://sandbox.wealthapi.eu/webform/abc123'
        )
      })
    })

    it('shows error when initiate bank connection fails', async () => {
      setAuthenticated()
      mockFetchResponses([
        { ok: true, data: MOCK_EXCHANGES },
        { ok: true, data: [] },
        { ok: false, data: { detail: 'Bank connection failed' }, status: 500 },
      ])

      render(
        <AuthProvider>
          <ExchangeConnectionsPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('add-connection-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('add-connection-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('bank-connect-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('bank-connect-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('form-error')).toBeInTheDocument()
        expect(screen.getByTestId('form-error')).toHaveTextContent('Bank connection failed')
      })
    })

    it('shows connecting state while initiating', async () => {
      setAuthenticated()

      let resolveInitiate: (value: unknown) => void
      const initiatePromise = new Promise((resolve) => {
        resolveInitiate = resolve
      })

      let callIndex = 0
      global.fetch = jest.fn((() => {
        callIndex++
        if (callIndex <= 2) {
          const data = callIndex === 1 ? MOCK_EXCHANGES : []
          return Promise.resolve({ ok: true, status: 200, json: async () => data })
        }
        return initiatePromise.then(() => ({
          ok: true,
          status: 200,
          json: async () => ({
            id: 'bc-123',
            web_form_url: 'https://sandbox.wealthapi.eu/webform/abc123',
            process_id: 'proc-456',
          }),
        }))
      }) as jest.Mock) as jest.Mock

      render(
        <AuthProvider>
          <ExchangeConnectionsPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('add-connection-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('add-connection-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('bank-connect-btn')).toBeInTheDocument()
      })

      await userEvent.click(screen.getByTestId('bank-connect-btn'))

      // Should show connecting state
      await waitFor(() => {
        expect(screen.getByTestId('bank-connect-btn')).toHaveTextContent(/connecting/i)
      })

      // Resolve to clean up
      await act(async () => {
        resolveInitiate!(undefined)
      })
    })
  })

  // -------------------------------------------------------------------------
  // Callback page: handles return from WealthAPI web form
  // -------------------------------------------------------------------------

  describe('WealthAPI Callback Page', () => {
    beforeEach(() => {
      // Reset search params for each test
      for (const key of Array.from(mockSearchParams.keys())) {
        mockSearchParams.delete(key)
      }
    })

    it('shows success and polls sync status on valid callback', async () => {
      setAuthenticated()
      mockSearchParams.set('id', 'bc-123')
      mockSearchParams.set('process_id', 'proc-456')
      mockSearchParams.set('status', 'COMPLETED')

      mockFetchResponses([
        // Poll sync status
        {
          ok: true,
          data: {
            status: 'COMPLETED',
            bank_connection_id: 'bc-123',
            accounts: [
              { id: 'acc-1', name: 'Checking Account', iban: 'DE89...1234', balance: 1500.0 },
            ],
          },
        },
      ])

      render(
        <AuthProvider>
          <WealthApiCallbackPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('callback-success')).toBeInTheDocument()
      })

      await waitFor(() => {
        expect(screen.getByText(/Checking Account/)).toBeInTheDocument()
      })
    })

    it('shows error state when callback has error status', async () => {
      setAuthenticated()
      mockSearchParams.set('status', 'FAILED')
      mockSearchParams.set('error', 'User cancelled authentication')

      render(
        <AuthProvider>
          <WealthApiCallbackPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('callback-error')).toBeInTheDocument()
        expect(screen.getByText(/User cancelled authentication/i)).toBeInTheDocument()
      })
    })

    it('shows pending state while polling for sync completion', async () => {
      setAuthenticated()
      mockSearchParams.set('id', 'bc-123')
      mockSearchParams.set('process_id', 'proc-456')
      mockSearchParams.set('status', 'COMPLETED')

      mockFetchResponses([
        // First poll: still syncing
        {
          ok: true,
          data: { status: 'RUNNING', progress: 50 },
        },
      ])

      render(
        <AuthProvider>
          <WealthApiCallbackPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('sync-progress')).toBeInTheDocument()
      })
    })

    it('provides link back to exchanges page', async () => {
      setAuthenticated()
      mockSearchParams.set('id', 'bc-123')
      mockSearchParams.set('process_id', 'proc-456')
      mockSearchParams.set('status', 'COMPLETED')

      mockFetchResponses([
        {
          ok: true,
          data: { status: 'COMPLETED', bank_connection_id: 'bc-123', accounts: [] },
        },
      ])

      render(
        <AuthProvider>
          <WealthApiCallbackPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('back-to-exchanges')).toBeInTheDocument()
      })
    })

    it('handles missing callback params gracefully', async () => {
      setAuthenticated()
      // No search params set

      render(
        <AuthProvider>
          <WealthApiCallbackPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('callback-error')).toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // Connection card: show bank connections from WealthAPI
  // -------------------------------------------------------------------------

  describe('Bank Connection Display', () => {
    it('shows bank connection card with account info', async () => {
      setAuthenticated()
      mockFetchResponses([
        { ok: true, data: MOCK_EXCHANGES },
        {
          ok: true,
          data: [
            {
              id: 1,
              user_id: 1,
              exchange_name: 'trade_republic',
              is_active: true,
              additional_config: JSON.stringify({
                bank_connection_id: 'bc-123',
                connection_type: 'wealthapi',
              }),
              last_synced_at: '2026-04-16T10:00:00Z',
              created_at: '2026-04-16T09:00:00Z',
              updated_at: '2026-04-16T10:00:00Z',
              api_key_masked: 'bank-connection',
            },
          ],
        },
      ])

      render(
        <AuthProvider>
          <ExchangeConnectionsPage />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('connection-card-trade_republic')).toBeInTheDocument()
      })

      // Should show "Bank Connected" indicator instead of API key masked
      expect(screen.getByText(/bank connected/i)).toBeInTheDocument()
    })
  })
})
