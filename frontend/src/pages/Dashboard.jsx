import { useState, useEffect, useRef } from 'react'
import { api } from '../api'
import ConfigModal from '../components/ConfigModal'

const INACTIVITY_HOURS = 5

export default function Dashboard({ user, onLogout }) {
  const [botStatus, setBotStatus]     = useState(null)
  const [loading, setLoading]         = useState(false)
  const [showConfig, setShowConfig]   = useState(false)
  const [error, setError]             = useState('')
  const [toast, setToast]             = useState(null)
  const [countdown, setCountdown]     = useState(null)
  const timerRef                      = useRef(null)
  const toastTimerRef                 = useRef(null)

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30_000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    clearInterval(timerRef.current)
    if (botStatus?.running && botStatus?.last_activity) {
      const tick = () => {
        const last      = new Date(botStatus.last_activity)
        const deadline  = new Date(last.getTime() + INACTIVITY_HOURS * 3600_000)
        const remaining = deadline - Date.now()
        setCountdown(remaining > 0 ? remaining : 0)
      }
      tick()
      timerRef.current = setInterval(tick, 1000)
    } else {
      setCountdown(null)
    }
    return () => clearInterval(timerRef.current)
  }, [botStatus])

  async function fetchStatus() {
    try {
      const data = await api.get('/api/bot/status')
      setBotStatus(data)
    } catch (e) {
      console.error(e)
    }
  }

  function showToast(message, type = 'error') {
    clearTimeout(toastTimerRef.current)
    setToast({ message, type })
    toastTimerRef.current = setTimeout(() => setToast(null), 5000)
  }

  async function toggleBot() {
    setLoading(true)
    setError('')
    const action = botStatus?.running ? 'stop' : 'start'
    try {
      await api.post(`/api/bot/${action}`)
      await fetchStatus()
    } catch (e) {
      const msg = e.message || `Failed to ${action} bot`
      setError(msg)
      showToast(msg)
    }
    setLoading(false)
  }

  function formatCountdown(ms) {
    if (ms === null) return ''
    const h = Math.floor(ms / 3_600_000)
    const m = Math.floor((ms % 3_600_000) / 60_000)
    const s = Math.floor((ms % 60_000) / 1000)
    return `${h}h ${m}m ${s}s`
  }

  const running = botStatus?.running ?? false

  return (
    <div className="min-h-screen bg-twitch-dark p-6">
      {/* Header */}
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            <div>
              <h1 className="text-white font-bold text-xl">Twitch AI Bot</h1>
              <p className="text-twitch-muted text-sm">@{user.username}</p>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="text-twitch-muted hover:text-white text-sm transition-colors"
          >
            Logout
          </button>
        </div>

        {/* Bot status card */}
        <div className="bg-twitch-card border border-twitch-border rounded-xl p-6 mb-4">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-white font-semibold text-lg mb-1">Chat Bot</h2>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${running ? 'bg-green-400' : 'bg-twitch-muted'}`} />
                <span className={`text-sm ${running ? 'text-green-400' : 'text-twitch-muted'}`}>
                  {running ? 'Running' : 'Stopped'}
                </span>
              </div>
            </div>

            <button
              onClick={toggleBot}
              disabled={loading}
              className={`px-6 py-2.5 rounded-lg font-semibold transition-colors disabled:opacity-50 ${
                running
                  ? 'bg-red-600 hover:bg-red-500 text-white'
                  : 'bg-twitch-purple hover:bg-purple-500 text-white'
              }`}
            >
              {loading ? '…' : running ? 'Stop Bot' : 'Start Bot'}
            </button>
          </div>

          {running && countdown !== null && (
            <div className="bg-twitch-dark rounded-lg p-3">
              <p className="text-twitch-muted text-xs mb-1">Auto-stop after 5h inactivity</p>
              <p className="text-white font-mono text-sm">
                {countdown > 0 ? `${formatCountdown(countdown)} remaining` : 'Stopping soon…'}
              </p>
            </div>
          )}

          {error && (
            <div className="mt-4 bg-red-900/30 border border-red-700 rounded-lg p-3 text-red-300 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Config button */}
        <button
          onClick={() => setShowConfig(true)}
          className="w-full bg-twitch-card border border-twitch-border hover:border-twitch-purple rounded-xl p-4 text-left transition-colors group"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xl">⚙️</span>
              <div>
                <p className="text-white font-medium">Configuration</p>
                <p className="text-twitch-muted text-sm">AI provider, model, system prompt, bot settings</p>
              </div>
            </div>
            <span className="text-twitch-muted group-hover:text-white transition-colors">›</span>
          </div>
        </button>

        {/* Commands reference */}
        <div className="mt-4 bg-twitch-card border border-twitch-border rounded-xl p-4">
          <p className="text-twitch-muted text-xs uppercase tracking-wide mb-3">Chat Commands</p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {['!ask [question]', '!joke', '!fact', '!roast [@user]', '!help'].map(cmd => (
              <span key={cmd} className="font-mono text-twitch-purple bg-twitch-dark rounded px-2 py-1">
                {cmd}
              </span>
            ))}
          </div>
        </div>
      </div>

      {showConfig && (
        <ConfigModal
          onClose={() => setShowConfig(false)}
          onSaved={() => { setShowConfig(false); fetchStatus() }}
        />
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-start gap-3 bg-red-900 border border-red-600 text-red-200 text-sm rounded-xl px-4 py-3 shadow-lg max-w-sm animate-fade-in">
          <span className="flex-1">{toast.message}</span>
          <button onClick={() => setToast(null)} className="text-red-400 hover:text-white leading-none mt-0.5">✕</button>
        </div>
      )}
    </div>
  )
}
