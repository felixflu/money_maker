import { render, screen } from '@testing-library/react'
import Home from '@/app/page'

describe('Home', () => {
  it('renders the application name', () => {
    render(<Home />)
    const heading = screen.getByRole('heading', { name: /money maker/i })
    expect(heading).toBeInTheDocument()
  })

  it('renders welcome message', () => {
    render(<Home />)
    const welcomeText = screen.getByText(/welcome to the money maker application/i)
    expect(welcomeText).toBeInTheDocument()
  })

  it('renders frontend status', () => {
    render(<Home />)
    const statusText = screen.getByText(/frontend is running successfully/i)
    expect(statusText).toBeInTheDocument()
  })
})
