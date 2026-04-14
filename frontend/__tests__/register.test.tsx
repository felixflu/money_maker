import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RegisterPage from '@/app/register/page'
import { AuthProvider } from '@/app/AuthContext'
import '@testing-library/jest-dom'

const mockPush = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

beforeEach(() => {
  global.fetch = jest.fn() as jest.Mock
})

afterEach(() => {
  jest.restoreAllMocks()
  localStorage.clear()
  mockPush.mockClear()
})

describe('Register Page', () => {
  it('renders register form', () => {
    render(
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    )

    expect(screen.getByRole('heading', { name: /register/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /register/i })).toBeInTheDocument()
  })

  it('has link to login page', () => {
    render(
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    )

    const loginLink = screen.getByRole('link', { name: /login/i })
    expect(loginLink).toHaveAttribute('href', '/login')
  })

  it('shows error when passwords do not match', async () => {
    const user = userEvent.setup()

    render(
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    )

    await user.type(screen.getByLabelText(/^email$/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'different')
    await user.click(screen.getByRole('button', { name: /register/i }))

    await waitFor(() => {
      expect(screen.getByTestId('register-error')).toHaveTextContent(/passwords do not match/i)
    })

    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('submits register form and redirects to login on success', async () => {
    const user = userEvent.setup()
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: '1', email: 'test@example.com' }),
    })

    render(
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    )

    await user.type(screen.getByLabelText(/^email$/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /register/i }))

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
      })
    })

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/login')
    })
  })

  it('shows error on registration failure', async () => {
    const user = userEvent.setup()
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ message: 'Email already exists' }),
    })

    render(
      <AuthProvider>
        <RegisterPage />
      </AuthProvider>
    )

    await user.type(screen.getByLabelText(/^email$/i), 'existing@example.com')
    await user.type(screen.getByLabelText(/^password$/i), 'password123')
    await user.type(screen.getByLabelText(/confirm password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /register/i }))

    await waitFor(() => {
      expect(screen.getByTestId('register-error')).toHaveTextContent(/email already exists/i)
    })
  })
})
