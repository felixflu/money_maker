import Link from 'next/link'

export default function Home() {
  return (
    <main style={{ maxWidth: '600px', margin: '4rem auto', padding: '2rem', fontFamily: 'sans-serif', textAlign: 'center' }}>
      <h1>Money Maker</h1>
      <p>Welcome to the Money Maker application.</p>
      <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', justifyContent: 'center' }}>
        <Link
          href="/login"
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: '#0070f3',
            color: 'white',
            textDecoration: 'none',
            borderRadius: '4px',
          }}
        >
          Login
        </Link>
        <Link
          href="/register"
          style={{
            padding: '0.75rem 2rem',
            backgroundColor: 'white',
            color: '#0070f3',
            textDecoration: 'none',
            borderRadius: '4px',
            border: '1px solid #0070f3',
          }}
        >
          Register
        </Link>
      </div>
    </main>
  )
}
