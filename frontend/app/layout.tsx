import type { Metadata } from 'next'
import { AuthProvider } from './AuthContext'

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
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}
