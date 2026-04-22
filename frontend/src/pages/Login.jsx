const CLIENT_ID    = import.meta.env.VITE_TWITCH_CLIENT_ID
const REDIRECT_URI = `${window.location.origin}/callback`
const SCOPES       = 'user:read:email'

function randomState() {
  return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2)
}

export default function Login() {
  function handleLogin() {
    const state = randomState()
    sessionStorage.setItem('oauth_state', state)

    const url = new URL('https://id.twitch.tv/oauth2/authorize')
    url.searchParams.set('client_id',     CLIENT_ID)
    url.searchParams.set('redirect_uri',  REDIRECT_URI)
    url.searchParams.set('response_type', 'code')
    url.searchParams.set('scope',         SCOPES)
    url.searchParams.set('state',         state)

    window.location.href = url.toString()
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen gap-8">
      <div className="text-center">
        <div className="text-5xl mb-4">🤖</div>
        <h1 className="text-3xl font-bold text-white mb-2">Twitch AI Bot</h1>
        <p className="text-twitch-muted">AI-powered chat bot for your stream</p>
      </div>

      <button
        onClick={handleLogin}
        className="flex items-center gap-3 bg-twitch-purple hover:bg-purple-500 transition-colors text-white font-semibold px-8 py-3 rounded-lg text-lg"
      >
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor">
          <path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/>
        </svg>
        Login with Twitch
      </button>

      <p className="text-twitch-muted text-sm max-w-sm text-center">
        Connect your Twitch account to configure and manage your AI chat bot
      </p>
    </div>
  )
}
