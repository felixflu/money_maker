'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '../AuthContext'

interface NavItem {
  label: string
  href: string
}

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Exchange Connections', href: '/exchanges' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      {/* Mobile hamburger button */}
      <button
        data-testid="sidebar-toggle"
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
        style={{
          position: 'fixed',
          top: '1rem',
          left: '1rem',
          zIndex: 1100,
          display: 'none',
          background: '#1a1a2e',
          color: '#fff',
          border: 'none',
          borderRadius: '4px',
          padding: '0.5rem 0.75rem',
          fontSize: '1.25rem',
          cursor: 'pointer',
          // Media query handled via className below
        }}
        className="sidebar-toggle"
      >
        {mobileOpen ? '\u2715' : '\u2630'}
      </button>

      {/* Overlay for mobile */}
      {mobileOpen && (
        <div
          data-testid="sidebar-overlay"
          onClick={() => setMobileOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            zIndex: 999,
          }}
          className="sidebar-overlay"
        />
      )}

      <aside
        data-testid="sidebar"
        className={mobileOpen ? 'sidebar sidebar-open' : 'sidebar'}
        style={{
          width: '240px',
          minHeight: '100vh',
          backgroundColor: '#1a1a2e',
          color: '#e0e0e0',
          display: 'flex',
          flexDirection: 'column',
          padding: '1.5rem 0',
          flexShrink: 0,
        }}
      >
        <div style={{ padding: '0 1.5rem', marginBottom: '2rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 700 }}>
            Money Maker
          </h2>
        </div>

        <nav style={{ flex: 1 }}>
          {navItems.map((item) => {
            const isActive = pathname === item.href
            return (
              <Link
                key={item.href}
                href={item.href}
                data-testid={`nav-${item.href.slice(1) || 'home'}`}
                onClick={() => setMobileOpen(false)}
                style={{
                  display: 'block',
                  padding: '0.75rem 1.5rem',
                  color: isActive ? '#fff' : '#a0a0b8',
                  backgroundColor: isActive ? '#16213e' : 'transparent',
                  textDecoration: 'none',
                  fontSize: '0.9375rem',
                  borderLeft: isActive ? '3px solid #0070f3' : '3px solid transparent',
                  transition: 'background-color 0.15s, color 0.15s',
                }}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div style={{ padding: '0 1.5rem', borderTop: '1px solid #2a2a4a', paddingTop: '1rem' }}>
          <button
            data-testid="sidebar-logout"
            onClick={logout}
            style={{
              width: '100%',
              padding: '0.5rem',
              backgroundColor: 'transparent',
              color: '#a0a0b8',
              border: '1px solid #2a2a4a',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            Log out
          </button>
        </div>
      </aside>

      <style>{`
        @media (max-width: 768px) {
          .sidebar-toggle {
            display: block !important;
          }
          .sidebar {
            position: fixed !important;
            left: -240px;
            top: 0;
            z-index: 1000;
            transition: left 0.2s ease;
          }
          .sidebar-open {
            left: 0 !important;
          }
        }
      `}</style>
    </>
  )
}
