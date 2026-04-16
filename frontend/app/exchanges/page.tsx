'use client'

import { useEffect, useState, useCallback } from 'react'
import { ProtectedRoute } from '../ProtectedRoute'
import { SupportedExchange, ExchangeConnection, WEALTHAPI_REDIRECT_EXCHANGES } from '../types'

const STORAGE_KEY = 'mm_auth_tokens'

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

const SYNC_ENDPOINT_MAP: Record<string, string> = {
  trade_republic: 'trade-republic',
  coinbase: 'coinbase',
  mexc: 'mexc',
  bitpanda: 'bitpanda',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  return new Date(dateStr).toLocaleString()
}

function isBankConnection(connection: ExchangeConnection): boolean {
  if (!connection.additional_config) return false
  try {
    const config = JSON.parse(connection.additional_config)
    return config.connection_type === 'wealthapi'
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// Add Connection Form
// ---------------------------------------------------------------------------

function AddConnectionForm({
  exchanges,
  existingNames,
  onCreated,
  onCancel,
}: {
  exchanges: SupportedExchange[]
  existingNames: Set<string>
  onCreated: () => void
  onCancel: () => void
}) {
  const available = exchanges.filter((e) => !existingNames.has(e.name))
  const [selectedExchange, setSelectedExchange] = useState(available[0]?.name || '')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState<{ valid: boolean; message: string } | null>(null)

  const selected = exchanges.find((e) => e.name === selectedExchange)
  const needsSecret = selected?.requires_api_secret ?? true
  const isRedirectFlow = WEALTHAPI_REDIRECT_EXCHANGES.has(selectedExchange)
  const [connecting, setConnecting] = useState(false)

  async function handleBankConnect() {
    setConnecting(true)
    setError(null)
    try {
      const res = await fetch('/api/v1/wealthapi/bank-connections', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          exchange_name: selectedExchange,
          callback_url: `${window.location.origin}/exchanges/callback`,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Failed: ${res.status}`)
      }
      const data = await res.json()
      if (data.web_form_url) {
        window.location.assign(data.web_form_url)
      } else {
        throw new Error('No web form URL returned')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to initiate bank connection')
      setConnecting(false)
    }
  }

  async function handleValidate() {
    setValidating(true)
    setValidationResult(null)
    try {
      const res = await fetch('/api/v1/exchanges/validate', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          exchange_name: selectedExchange,
          api_key: apiKey,
          api_secret: apiSecret || '',
        }),
      })
      const data = await res.json()
      setValidationResult({ valid: data.valid, message: data.message })
    } catch {
      setValidationResult({ valid: false, message: 'Network error' })
    } finally {
      setValidating(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const res = await fetch('/api/v1/exchanges/connections', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          exchange_name: selectedExchange,
          api_key: apiKey,
          api_secret: apiSecret || '',
          is_active: true,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Failed: ${res.status}`)
      }
      onCreated()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create connection')
    } finally {
      setSubmitting(false)
    }
  }

  if (available.length === 0) {
    return (
      <div style={{ padding: '1.5rem', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e5e5', marginBottom: '1.5rem' }}>
        <p style={{ margin: 0, color: '#666' }}>All supported exchanges are already connected.</p>
        <button onClick={onCancel} style={{ marginTop: '1rem', padding: '0.5rem 1rem', backgroundColor: '#e5e5e5', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          Close
        </button>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="add-connection-form"
      style={{ padding: '1.5rem', backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e5e5e5', marginBottom: '1.5rem' }}
    >
      <h3 style={{ margin: '0 0 1rem 0' }}>Add Exchange Connection</h3>

      {error && (
        <div data-testid="form-error" style={{ padding: '0.75rem', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '4px', marginBottom: '1rem', fontSize: '0.875rem' }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: '1rem' }}>
        <label htmlFor="exchange-select" style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 600, fontSize: '0.875rem' }}>
          Exchange
        </label>
        <select
          id="exchange-select"
          data-testid="exchange-select"
          value={selectedExchange}
          onChange={(e) => {
            setSelectedExchange(e.target.value)
            setValidationResult(null)
          }}
          style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.875rem' }}
        >
          {available.map((ex) => (
            <option key={ex.name} value={ex.name}>{ex.display_name}</option>
          ))}
        </select>
        {selected && (
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: '#666' }}>{selected.description}</p>
        )}
      </div>

      {isRedirectFlow ? (
        <>
          <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem', color: '#555' }}>
            You will be redirected to your bank&apos;s login page to authorize the connection.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              data-testid="bank-connect-btn"
              onClick={handleBankConnect}
              disabled={connecting}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#0070f3',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: connecting ? 'wait' : 'pointer',
                fontSize: '0.875rem',
                fontWeight: 600,
              }}
            >
              {connecting ? 'Connecting...' : 'Connect via Bank'}
            </button>
            <button
              type="button"
              onClick={onCancel}
              style={{ padding: '0.5rem 1rem', backgroundColor: '#e5e5e5', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.875rem' }}
            >
              Cancel
            </button>
          </div>
        </>
      ) : (
        <>
          <div style={{ marginBottom: '1rem' }}>
            <label htmlFor="api-key" style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 600, fontSize: '0.875rem' }}>
              API Key
            </label>
            <input
              id="api-key"
              data-testid="api-key-input"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
              placeholder="Enter your API key"
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.875rem', boxSizing: 'border-box' }}
            />
          </div>

          {needsSecret && (
            <div style={{ marginBottom: '1rem' }}>
              <label htmlFor="api-secret" style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 600, fontSize: '0.875rem' }}>
                API Secret
              </label>
              <input
                id="api-secret"
                data-testid="api-secret-input"
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                required
                placeholder="Enter your API secret"
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.875rem', boxSizing: 'border-box' }}
              />
            </div>
          )}

          {validationResult && (
            <div
              data-testid="validation-result"
              style={{
                padding: '0.75rem',
                backgroundColor: validationResult.valid ? '#f0fdf4' : '#fef2f2',
                color: validationResult.valid ? '#16a34a' : '#dc2626',
                borderRadius: '4px',
                marginBottom: '1rem',
                fontSize: '0.875rem',
              }}
            >
              {validationResult.message}
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              data-testid="validate-btn"
              onClick={handleValidate}
              disabled={validating || !apiKey || (needsSecret && !apiSecret)}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#f5f5f5',
                border: '1px solid #ccc',
                borderRadius: '4px',
                cursor: validating ? 'wait' : 'pointer',
                fontSize: '0.875rem',
              }}
            >
              {validating ? 'Validating...' : 'Validate'}
            </button>
            <button
              type="submit"
              data-testid="save-connection-btn"
              disabled={submitting || !apiKey || (needsSecret && !apiSecret)}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#0070f3',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: submitting ? 'wait' : 'pointer',
                fontSize: '0.875rem',
              }}
            >
              {submitting ? 'Saving...' : 'Save Connection'}
            </button>
            <button
              type="button"
              onClick={onCancel}
              style={{ padding: '0.5rem 1rem', backgroundColor: '#e5e5e5', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.875rem' }}
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </form>
  )
}

// ---------------------------------------------------------------------------
// Edit Connection Form
// ---------------------------------------------------------------------------

function EditConnectionForm({
  connection,
  exchange,
  onUpdated,
  onCancel,
}: {
  connection: ExchangeConnection
  exchange: SupportedExchange | undefined
  onUpdated: () => void
  onCancel: () => void
}) {
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [isActive, setIsActive] = useState(connection.is_active)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const needsSecret = exchange?.requires_api_secret ?? true

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    const body: Record<string, unknown> = { is_active: isActive }
    if (apiKey) body.api_key = apiKey
    if (apiSecret) body.api_secret = apiSecret

    try {
      const res = await fetch(`/api/v1/exchanges/connections/${connection.id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Failed: ${res.status}`)
      }
      onUpdated()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update connection')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="edit-connection-form"
      style={{ padding: '1rem', backgroundColor: '#fafafa', borderRadius: '4px', marginTop: '0.75rem' }}
    >
      {error && (
        <div style={{ padding: '0.5rem', backgroundColor: '#fef2f2', color: '#dc2626', borderRadius: '4px', marginBottom: '0.75rem', fontSize: '0.8125rem' }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: '0.75rem' }}>
        <label htmlFor={`edit-key-${connection.id}`} style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 600, fontSize: '0.8125rem' }}>
          New API Key (leave blank to keep current)
        </label>
        <input
          id={`edit-key-${connection.id}`}
          data-testid="edit-api-key-input"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="New API key"
          style={{ width: '100%', padding: '0.4rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.8125rem', boxSizing: 'border-box' }}
        />
      </div>

      {needsSecret && (
        <div style={{ marginBottom: '0.75rem' }}>
          <label htmlFor={`edit-secret-${connection.id}`} style={{ display: 'block', marginBottom: '0.25rem', fontWeight: 600, fontSize: '0.8125rem' }}>
            New API Secret (leave blank to keep current)
          </label>
          <input
            id={`edit-secret-${connection.id}`}
            data-testid="edit-api-secret-input"
            type="password"
            value={apiSecret}
            onChange={(e) => setApiSecret(e.target.value)}
            placeholder="New API secret"
            style={{ width: '100%', padding: '0.4rem', borderRadius: '4px', border: '1px solid #ccc', fontSize: '0.8125rem', boxSizing: 'border-box' }}
          />
        </div>
      )}

      <div style={{ marginBottom: '0.75rem' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem' }}>
          <input
            type="checkbox"
            data-testid="edit-active-checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Active
        </label>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button
          type="submit"
          data-testid="update-connection-btn"
          disabled={submitting}
          style={{ padding: '0.4rem 0.75rem', backgroundColor: '#0070f3', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8125rem' }}
        >
          {submitting ? 'Updating...' : 'Update'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          style={{ padding: '0.4rem 0.75rem', backgroundColor: '#e5e5e5', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8125rem' }}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Connection Card
// ---------------------------------------------------------------------------

function ConnectionCard({
  connection,
  exchange,
  onDeleted,
  onUpdated,
}: {
  connection: ExchangeConnection
  exchange: SupportedExchange | undefined
  onDeleted: () => void
  onUpdated: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ success: boolean; message: string } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  async function handleDelete() {
    setDeleting(true)
    try {
      const res = await fetch(`/api/v1/exchanges/connections/${connection.id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      if (!res.ok && res.status !== 204) {
        throw new Error(`Failed: ${res.status}`)
      }
      onDeleted()
    } catch {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  async function handleSync() {
    setSyncing(true)
    setSyncResult(null)
    const slug = SYNC_ENDPOINT_MAP[connection.exchange_name]
    if (!slug) {
      setSyncResult({ success: false, message: 'Unknown exchange' })
      setSyncing(false)
      return
    }
    try {
      const res = await fetch(`/api/v1/exchanges/${slug}/sync/${connection.id}`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ sync_transactions: true }),
      })
      const data = await res.json()
      setSyncResult({ success: data.success, message: data.message })
      if (data.success) onUpdated()
    } catch {
      setSyncResult({ success: false, message: 'Network error during sync' })
    } finally {
      setSyncing(false)
    }
  }

  const displayName = exchange?.display_name || connection.exchange_name

  return (
    <div
      data-testid={`connection-card-${connection.exchange_name}`}
      style={{
        padding: '1.25rem',
        backgroundColor: '#fff',
        borderRadius: '8px',
        border: '1px solid #e5e5e5',
        marginBottom: '1rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '1.125rem' }}>{displayName}</h3>
          {exchange && (
            <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.8125rem', color: '#666' }}>{exchange.description}</p>
          )}
        </div>
        <span
          data-testid={`connection-status-${connection.exchange_name}`}
          style={{
            padding: '0.25rem 0.5rem',
            borderRadius: '4px',
            fontSize: '0.75rem',
            fontWeight: 600,
            backgroundColor: connection.is_active ? '#f0fdf4' : '#f5f5f5',
            color: connection.is_active ? '#16a34a' : '#999',
          }}
        >
          {connection.is_active ? 'Active' : 'Inactive'}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '2rem', fontSize: '0.8125rem', color: '#555', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
        {isBankConnection(connection) ? (
          <span style={{ color: '#16a34a', fontWeight: 600 }}>Bank Connected</span>
        ) : (
          <span>API Key: <code style={{ backgroundColor: '#f5f5f5', padding: '0.125rem 0.25rem', borderRadius: '2px' }}>{connection.api_key_masked || '****'}</code></span>
        )}
        <span>Last synced: {formatDate(connection.last_synced_at)}</span>
        <span>Added: {formatDate(connection.created_at)}</span>
      </div>

      {exchange && exchange.supported_features.length > 0 && (
        <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
          {exchange.supported_features.map((f) => (
            <span
              key={f}
              style={{
                padding: '0.125rem 0.5rem',
                backgroundColor: '#f0f4ff',
                color: '#3b5998',
                borderRadius: '12px',
                fontSize: '0.75rem',
              }}
            >
              {f.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      {syncResult && (
        <div
          data-testid={`sync-result-${connection.exchange_name}`}
          style={{
            padding: '0.5rem 0.75rem',
            backgroundColor: syncResult.success ? '#f0fdf4' : '#fef2f2',
            color: syncResult.success ? '#16a34a' : '#dc2626',
            borderRadius: '4px',
            marginBottom: '0.75rem',
            fontSize: '0.8125rem',
          }}
        >
          {syncResult.message}
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button
          data-testid={`sync-btn-${connection.exchange_name}`}
          onClick={handleSync}
          disabled={syncing || !connection.is_active}
          style={{
            padding: '0.4rem 0.75rem',
            backgroundColor: '#0070f3',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: syncing ? 'wait' : 'pointer',
            fontSize: '0.8125rem',
            opacity: !connection.is_active ? 0.5 : 1,
          }}
        >
          {syncing ? 'Syncing...' : 'Sync Now'}
        </button>
        <button
          data-testid={`edit-btn-${connection.exchange_name}`}
          onClick={() => setEditing(!editing)}
          style={{ padding: '0.4rem 0.75rem', backgroundColor: '#f5f5f5', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8125rem' }}
        >
          {editing ? 'Cancel Edit' : 'Edit'}
        </button>
        {!confirmDelete ? (
          <button
            data-testid={`delete-btn-${connection.exchange_name}`}
            onClick={() => setConfirmDelete(true)}
            style={{ padding: '0.4rem 0.75rem', backgroundColor: '#fff', border: '1px solid #dc2626', color: '#dc2626', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8125rem' }}
          >
            Delete
          </button>
        ) : (
          <span style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8125rem', color: '#dc2626' }}>Confirm?</span>
            <button
              data-testid={`confirm-delete-btn-${connection.exchange_name}`}
              onClick={handleDelete}
              disabled={deleting}
              style={{ padding: '0.4rem 0.75rem', backgroundColor: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8125rem' }}
            >
              {deleting ? 'Deleting...' : 'Yes, Delete'}
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              style={{ padding: '0.4rem 0.75rem', backgroundColor: '#e5e5e5', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8125rem' }}
            >
              No
            </button>
          </span>
        )}
      </div>

      {editing && (
        <EditConnectionForm
          connection={connection}
          exchange={exchange}
          onUpdated={() => { setEditing(false); onUpdated() }}
          onCancel={() => setEditing(false)}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page Content
// ---------------------------------------------------------------------------

function ExchangeConnectionsContent() {
  const [exchanges, setExchanges] = useState<SupportedExchange[]>([])
  const [connections, setConnections] = useState<ExchangeConnection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)

  const loadData = useCallback(async () => {
    try {
      const [exRes, connRes] = await Promise.all([
        fetch('/api/v1/exchanges/supported', { headers: authHeaders() }),
        fetch('/api/v1/exchanges/connections', { headers: authHeaders() }),
      ])

      if (!exRes.ok) throw new Error(`Failed to load exchanges: ${exRes.status}`)
      if (!connRes.ok) throw new Error(`Failed to load connections: ${connRes.status}`)

      const exData = await exRes.json()
      const connData = await connRes.json()

      setExchanges(exData.exchanges || [])
      setConnections(connData)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  if (isLoading) {
    return (
      <div data-testid="exchanges-loading" style={{ padding: '2rem', textAlign: 'center' }}>
        <p>Loading exchange connections...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div data-testid="exchanges-error" style={{ padding: '2rem', color: '#dc2626' }}>
        <p>{error}</p>
        <button onClick={() => { setIsLoading(true); loadData() }} style={{ padding: '0.5rem 1rem', backgroundColor: '#0070f3', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          Retry
        </button>
      </div>
    )
  }

  const existingNames = new Set(connections.map((c) => c.exchange_name))
  const exchangeMap = new Map(exchanges.map((e) => [e.name, e]))

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0 }}>Exchange Connections</h1>
        {!showAddForm && (
          <button
            data-testid="add-connection-btn"
            onClick={() => setShowAddForm(true)}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#0070f3',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.875rem',
              fontWeight: 600,
            }}
          >
            + Add Connection
          </button>
        )}
      </div>

      {showAddForm && (
        <AddConnectionForm
          exchanges={exchanges}
          existingNames={existingNames}
          onCreated={() => { setShowAddForm(false); loadData() }}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      {connections.length === 0 ? (
        <div
          data-testid="no-connections"
          style={{
            padding: '2rem',
            textAlign: 'center',
            color: '#666',
            backgroundColor: '#fafafa',
            borderRadius: '8px',
            border: '1px dashed #ccc',
          }}
        >
          <p style={{ fontSize: '1.125rem', margin: '0 0 0.5rem 0' }}>No exchange connections yet</p>
          <p style={{ fontSize: '0.875rem', margin: 0 }}>
            Connect your exchange accounts to start tracking your portfolio.
          </p>
        </div>
      ) : (
        <div data-testid="connections-list">
          {connections.map((conn) => (
            <ConnectionCard
              key={conn.id}
              connection={conn}
              exchange={exchangeMap.get(conn.exchange_name)}
              onDeleted={loadData}
              onUpdated={loadData}
            />
          ))}
        </div>
      )}

      {exchanges.length > 0 && (
        <section style={{ marginTop: '2rem' }}>
          <h2 style={{ fontSize: '1rem', color: '#666', marginBottom: '0.75rem' }}>Supported Exchanges</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '0.75rem' }}>
            {exchanges.map((ex) => {
              const connected = existingNames.has(ex.name)
              return (
                <div
                  key={ex.name}
                  data-testid={`supported-exchange-${ex.name}`}
                  style={{
                    padding: '1rem',
                    backgroundColor: '#fff',
                    borderRadius: '8px',
                    border: connected ? '1px solid #16a34a' : '1px solid #e5e5e5',
                    opacity: connected ? 0.7 : 1,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h4 style={{ margin: 0, fontSize: '0.9375rem' }}>{ex.display_name}</h4>
                    {connected && (
                      <span style={{ fontSize: '0.75rem', color: '#16a34a', fontWeight: 600 }}>Connected</span>
                    )}
                  </div>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: '#666' }}>{ex.description}</p>
                </div>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}

export default function ExchangeConnectionsPage() {
  return (
    <ProtectedRoute>
      <ExchangeConnectionsContent />
    </ProtectedRoute>
  )
}
