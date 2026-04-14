import type { Metadata } from 'next'
import { AuthProvider } from './AuthContext'
import { AppShell } from './components/AppShell'

export const metadata: Metadata = {
  title: 'Money Maker',
  description: 'Money Maker Application',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>
        <AuthProvider>
          <AppShell>
            {children}
          </AppShell>
        </AuthProvider>
      </body>
    </html>
  )
}
