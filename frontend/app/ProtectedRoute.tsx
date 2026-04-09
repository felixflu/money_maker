'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from './AuthContext'

interface ProtectedRouteProps {
  children: React.ReactNode
  fallback?: React.ReactNode
}

export function ProtectedRoute({ children, fallback }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [isLoading, isAuthenticated, router])

  if (isLoading) {
    return (
      <div data-testid="auth-loading" style={{ padding: '2rem', textAlign: 'center' }}>
        Loading...
      </div>
    )
  }

  if (!isAuthenticated) {
    return fallback || (
      <div data-testid="auth-redirecting" style={{ padding: '2rem', textAlign: 'center' }}>
        Redirecting to login...
      </div>
    )
  }

  return <>{children}</>
}
