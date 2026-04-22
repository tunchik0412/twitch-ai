import { useState, useEffect } from 'react'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import { api } from './api'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code   = params.get('code')
    const state  = params.get('state')

    if (code) {
      handleCallback(code, state)
    } else {
      const token = localStorage.getItem('token')
      if (token) {
        api.get('/api/auth/me')
          .then(setUser)
          .catch(() => localStorage.removeItem('token'))
          .finally(() => setLoading(false))
      } else {
        setLoading(false)
      }
    }
  }, [])

  async function handleCallback(code, state) {
    const saved = sessionStorage.getItem('oauth_state')
    if (state !== saved) {
      setLoading(false)
      return
    }
    try {
      const redirectUri = `${window.location.origin}/callback`
      const data = await api.post('/api/auth/twitch', { code, redirect_uri: redirectUri })
      localStorage.setItem('token', data.token)
      setUser(data.user)
    } catch (e) {
      console.error('Auth failed:', e)
    }
    window.history.replaceState({}, '', '/')
    setLoading(false)
  }

  function handleLogout() {
    localStorage.clear()
    setUser(null)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-twitch-muted text-lg">Loading…</div>
      </div>
    )
  }

  if (!user) return <Login />
  return <Dashboard user={user} onLogout={handleLogout} />
}
