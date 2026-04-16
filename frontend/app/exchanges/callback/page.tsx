'use client'

import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import { ProtectedRoute } from '../../ProtectedRoute'
import { BankSyncStatus } from '../../types'

const STORAGE_KEY = 'mm_auth_tokens'
const POLL_INTERVAL_MS = 2000

function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null
  const stored = localStorage.getItem(STORAGE_KEY)
  if (!stored) return null
  try {
    const parsed = JSON.parse(stored)
    return parsed.accessToken || parsed.access_token || null
  } catch {
    return null
  }
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

function CallbackContent() {
  const searchParams = useSearchParams()
  const callbackStatus = searchParams.get('status')
  const callbackError = searchParams.get('error')
  const bankConnectionId = searchParams.get('id')
  const processId = searchParams.get('process_id')

  const [syncStatus, setSyncStatus] = useState<BankSyncStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const pollSyncStatus = useCallback(async () => {
    if (!processId) return

    try {
      const res = await fetch(
        `/api/v1/wealthapi/bank-connections/update-process/${processId}`,
        { headers: authHeaders() }
      )
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Failed: ${res.status}`)
      }
      const data: BankSyncStatus = await res.json()
      setSyncStatus(data)
      return data.status
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to check sync status')
      return 'FAILED'
    }
  }, [processId])

  useEffect(() => {
    // No params = invalid callback
    if (!callbackStatus && !bankConnectionId && !processId) {
      setError('Invalid callback: missing parameters')
      return
    }

    // Callback reported failure
    if (callbackStatus === 'FAILED') {
      setError(callbackError || 'Bank authentication failed')
      return
    }

    // Callback succeeded — poll for sync completion
    if (processId) {
      let cancelled = false

      async function poll() {
        const status = await pollSyncStatus()
        if (!cancelled && status === 'RUNNING') {
          setTimeout(poll, POLL_INTERVAL_MS)
        }
      }

      poll()
      return () => { cancelled = true }
    }
  }, [callbackStatus, callbackError, bankConnectionId, processId, pollSyncStatus])

  // Error state
  if (error || callbackStatus === 'FAILED') {
    return (
      <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
        <div
          data-testid="callback-error"
          style={{
            padding: '1.5rem',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '8px',
            color: '#dc2626',
            marginBottom: '1.5rem',
          }}
        >
          <h2 style={{ margin: '0 0 0.5rem 0' }}>Bank Connection Failed</h2>
          <p style={{ margin: 0 }}>{error || callbackError || 'Unknown error'}</p>
        </div>
        <a
          href="/exchanges"
          data-testid="back-to-exchanges"
          style={{
            display: 'inline-block',
            padding: '0.5rem 1rem',
            backgroundColor: '#0070f3',
            color: '#fff',
            borderRadius: '4px',
            textDecoration: 'none',
            fontSize: '0.875rem',
          }}
        >
          Back to Exchanges
        </a>
      </div>
    )
  }

  // Polling / in-progress state
  if (!syncStatus || syncStatus.status === 'RUNNING') {
    return (
      <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
        <div
          data-testid="sync-progress"
          style={{
            padding: '1.5rem',
            backgroundColor: '#f0f4ff',
            border: '1px solid #bfdbfe',
            borderRadius: '8px',
            marginBottom: '1.5rem',
          }}
        >
          <h2 style={{ margin: '0 0 0.5rem 0' }}>Syncing Bank Connection...</h2>
          <p style={{ margin: '0 0 0.5rem 0', color: '#555' }}>
            Your bank account is being synchronized. This may take a moment.
          </p>
          {syncStatus?.progress != null && (
            <div style={{ marginTop: '0.75rem' }}>
              <div
                style={{
                  height: '8px',
                  backgroundColor: '#e5e7eb',
                  borderRadius: '4px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${syncStatus.progress}%`,
                    backgroundColor: '#0070f3',
                    borderRadius: '4px',
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>
              <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: '#666' }}>
                {syncStatus.progress}% complete
              </p>
            </div>
          )}
        </div>
      </div>
    )
  }

  // Sync failed
  if (syncStatus.status === 'FAILED') {
    return (
      <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
        <div
          data-testid="callback-error"
          style={{
            padding: '1.5rem',
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '8px',
            color: '#dc2626',
            marginBottom: '1.5rem',
          }}
        >
          <h2 style={{ margin: '0 0 0.5rem 0' }}>Sync Failed</h2>
          <p style={{ margin: 0 }}>{syncStatus.error || 'Bank synchronization failed'}</p>
        </div>
        <a
          href="/exchanges"
          data-testid="back-to-exchanges"
          style={{
            display: 'inline-block',
            padding: '0.5rem 1rem',
            backgroundColor: '#0070f3',
            color: '#fff',
            borderRadius: '4px',
            textDecoration: 'none',
            fontSize: '0.875rem',
          }}
        >
          Back to Exchanges
        </a>
      </div>
    )
  }

  // Success — show connected accounts
  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <div
        data-testid="callback-success"
        style={{
          padding: '1.5rem',
          backgroundColor: '#f0fdf4',
          border: '1px solid #bbf7d0',
          borderRadius: '8px',
          marginBottom: '1.5rem',
        }}
      >
        <h2 style={{ margin: '0 0 0.5rem 0', color: '#16a34a' }}>
          Bank Connected Successfully
        </h2>
        <p style={{ margin: 0, color: '#555' }}>
          Your bank account has been connected and synchronized.
        </p>
      </div>

      {syncStatus.accounts && syncStatus.accounts.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.75rem 0' }}>Connected Accounts</h3>
          {syncStatus.accounts.map((account) => (
            <div
              key={account.id}
              style={{
                padding: '1rem',
                backgroundColor: '#fff',
                border: '1px solid #e5e5e5',
                borderRadius: '8px',
                marginBottom: '0.5rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <p style={{ margin: '0 0 0.25rem 0', fontWeight: 600 }}>{account.name}</p>
                  <p style={{ margin: 0, fontSize: '0.8125rem', color: '#666' }}>{account.iban}</p>
                </div>
                {account.balance != null && (
                  <span style={{ fontWeight: 600, fontSize: '1.125rem' }}>
                    {account.balance.toLocaleString('de-DE', { style: 'currency', currency: 'EUR' })}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <a
        href="/exchanges"
        data-testid="back-to-exchanges"
        style={{
          display: 'inline-block',
          padding: '0.5rem 1rem',
          backgroundColor: '#0070f3',
          color: '#fff',
          borderRadius: '4px',
          textDecoration: 'none',
          fontSize: '0.875rem',
        }}
      >
        Back to Exchanges
      </a>
    </div>
  )
}

export default function WealthApiCallbackPage() {
  return (
    <ProtectedRoute>
      <CallbackContent />
    </ProtectedRoute>
  )
}
