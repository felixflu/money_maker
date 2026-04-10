import { render, screen } from '@testing-library/react'
import HealthCheck from '@/app/health/page'

describe('HealthCheck', () => {
  it('renders health check heading', () => {
    render(<HealthCheck />)
    const heading = screen.getByRole('heading', { name: /health check/i })
    expect(heading).toBeInTheDocument()
  })

  it('displays health status', () => {
    render(<HealthCheck />)
    const status = screen.getByTestId('health-status')
    expect(status).toBeInTheDocument()
    expect(status).toHaveTextContent('Frontend is healthy')
  })

  it('is accessible', () => {
    render(<HealthCheck />)
    const main = screen.getByRole('main')
    expect(main).toBeInTheDocument()
  })
})
