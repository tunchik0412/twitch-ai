import { useState, useEffect } from 'react'
import { api } from '../api'

const PROVIDERS = {
  gemini: {
    name: 'Google Gemini',
    models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  },
  claude: {
    name: 'Anthropic Claude',
    models: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
  },
  openai: {
    name: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  },
}

const TABS = ['AI', 'Bot']

export default function ConfigModal({ onClose, onSaved }) {
  const [tab, setTab]         = useState('AI')
  const [form, setForm]       = useState(null)
  const [saving, setSaving]   = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState('')
  const [error, setError]     = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    api.get('/api/config').then(data => {
      setForm({
        ai_provider:         data.ai_provider || 'gemini',
        ai_model:            data.ai_model || 'gemini-2.0-flash',
        api_key:             '',
        has_api_key:         data.has_api_key,
        system_prompt:       data.system_prompt || '',
        temperature:         data.temperature ?? 0.7,
        max_tokens:          data.max_tokens ?? 300,
        bot_prefix:          data.bot_prefix || '!',
        cooldown:            data.cooldown ?? 5,
        twitch_bot_token:    '',
        has_bot_token:       data.has_bot_token,
        twitch_channel_name: data.twitch_channel_name || '',
      })
    }).catch(() => setError('Failed to load config'))
  }, [])

  function set(key, val) {
    setForm(f => ({ ...f, [key]: val }))
    setError('')
    setSuccess('')
  }

  function onProviderChange(provider) {
    const firstModel = PROVIDERS[provider]?.models[0] || ''
    setForm(f => ({ ...f, ai_provider: provider, ai_model: firstModel }))
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const payload = {
        ai_provider:         form.ai_provider,
        ai_model:            form.ai_model,
        system_prompt:       form.system_prompt,
        temperature:         form.temperature,
        max_tokens:          form.max_tokens,
        bot_prefix:          form.bot_prefix,
        cooldown:            form.cooldown,
        twitch_channel_name: form.twitch_channel_name,
      }
      if (form.api_key)         payload.api_key         = form.api_key
      if (form.twitch_bot_token) payload.twitch_bot_token = form.twitch_bot_token

      await api.post('/api/config', payload)
      setSuccess('Saved!')
      setForm(f => ({
        ...f,
        api_key:          '',
        twitch_bot_token: '',
        has_api_key:      f.has_api_key || !!f.api_key,
        has_bot_token:    f.has_bot_token || !!f.twitch_bot_token,
      }))
    } catch (e) {
      setError(e.message)
    }
    setSaving(false)
  }

  async function handleTest() {
    setTesting(true)
    setTestResult('')
    try {
      const data = await api.post('/api/generate', { prompt: 'Say hello in one sentence!' })
      setTestResult(data.reply)
    } catch (e) {
      setTestResult('Error: ' + e.message)
    }
    setTesting(false)
  }

  if (!form) {
    return (
      <Overlay onClose={onClose}>
        <div className="text-twitch-muted text-center py-8">Loading…</div>
      </Overlay>
    )
  }

  const models = PROVIDERS[form.ai_provider]?.models || []

  return (
    <Overlay onClose={onClose}>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-white font-bold text-xl">Configuration</h2>
        <button onClick={onClose} className="text-twitch-muted hover:text-white text-xl">×</button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-twitch-dark rounded-lg p-1">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === t ? 'bg-twitch-purple text-white' : 'text-twitch-muted hover:text-white'
            }`}
          >
            {t === 'AI' ? '🧠 AI Settings' : '🤖 Bot Settings'}
          </button>
        ))}
      </div>

      {tab === 'AI' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-twitch-muted text-xs mb-1.5 uppercase tracking-wide">AI Provider</label>
              <select
                value={form.ai_provider}
                onChange={e => onProviderChange(e.target.value)}
                className="w-full bg-twitch-dark border border-twitch-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-twitch-purple"
              >
                {Object.entries(PROVIDERS).map(([key, p]) => (
                  <option key={key} value={key}>{p.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-twitch-muted text-xs mb-1.5 uppercase tracking-wide">Model</label>
              <select
                value={form.ai_model}
                onChange={e => set('ai_model', e.target.value)}
                className="w-full bg-twitch-dark border border-twitch-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-twitch-purple"
              >
                {models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          <Field label={`API Key${form.has_api_key ? ' (saved — enter new to replace)' : ''}`}>
            <input
              type="password"
              value={form.api_key}
              onChange={e => set('api_key', e.target.value)}
              placeholder={form.has_api_key ? '••••••••••••••••' : 'Enter API key'}
              className={INPUT}
            />
          </Field>

          <Field label="System Prompt">
            <textarea
              value={form.system_prompt}
              onChange={e => set('system_prompt', e.target.value)}
              rows={4}
              className={INPUT + ' resize-none'}
              placeholder="You are a helpful AI assistant in a Twitch stream…"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label={`Temperature: ${form.temperature}`}>
              <input
                type="range" min="0" max="2" step="0.1"
                value={form.temperature}
                onChange={e => set('temperature', parseFloat(e.target.value))}
                className="w-full accent-twitch-purple"
              />
              <div className="flex justify-between text-twitch-muted text-xs mt-1">
                <span>Focused</span><span>Creative</span>
              </div>
            </Field>
            <Field label="Max Tokens">
              <input
                type="number" min="50" max="2000"
                value={form.max_tokens}
                onChange={e => set('max_tokens', parseInt(e.target.value))}
                className={INPUT}
              />
            </Field>
          </div>

          {/* Test */}
          <div className="border-t border-twitch-border pt-4">
            <button
              onClick={handleTest}
              disabled={testing || !form.has_api_key}
              className="text-sm text-twitch-purple hover:text-purple-300 disabled:opacity-40 transition-colors"
            >
              {testing ? 'Testing…' : '▶ Test AI response'}
            </button>
            {testResult && (
              <div className="mt-2 bg-twitch-dark rounded-lg p-3 text-sm text-white border border-twitch-border">
                {testResult}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'Bot' && (
        <div className="space-y-4">
          <Field label={`Twitch Bot Token${form.has_bot_token ? ' (saved — enter new to replace)' : ''}`}>
            <input
              type="password"
              value={form.twitch_bot_token}
              onChange={e => set('twitch_bot_token', e.target.value)}
              placeholder={form.has_bot_token ? '••••••••••••••••' : 'oauth:your_bot_token'}
              className={INPUT}
            />
            <p className="text-twitch-muted text-xs mt-1">
              Get from <a href="https://twitchtokengenerator.com" target="_blank" rel="noreferrer" className="text-twitch-purple hover:underline">twitchtokengenerator.com</a> — select "Bot Chat Token"
            </p>
          </Field>

          <Field label="Channel Name (to join)">
            <input
              type="text"
              value={form.twitch_channel_name}
              onChange={e => set('twitch_channel_name', e.target.value)}
              placeholder="your_channel_name"
              className={INPUT}
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Command Prefix">
              <input
                type="text" maxLength={3}
                value={form.bot_prefix}
                onChange={e => set('bot_prefix', e.target.value)}
                className={INPUT}
              />
            </Field>
            <Field label="Cooldown (seconds)">
              <input
                type="number" min="0" max="300"
                value={form.cooldown}
                onChange={e => set('cooldown', parseInt(e.target.value))}
                className={INPUT}
              />
            </Field>
          </div>

          <div className="bg-twitch-dark border border-twitch-border rounded-lg p-3 text-sm text-twitch-muted">
            Bot auto-stops after <span className="text-white">5 hours</span> of no commands.
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-6 pt-4 border-t border-twitch-border">
        <div className="text-sm">
          {error   && <span className="text-red-400">{error}</span>}
          {success && <span className="text-green-400">{success}</span>}
        </div>
        <div className="flex gap-3">
          <button onClick={onClose} className="px-4 py-2 text-twitch-muted hover:text-white transition-colors text-sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-twitch-purple hover:bg-purple-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </Overlay>
  )
}

function Overlay({ onClose, children }) {
  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-twitch-card border border-twitch-border rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-twitch-muted text-xs mb-1.5 uppercase tracking-wide">{label}</label>
      {children}
    </div>
  )
}

const INPUT = 'w-full bg-twitch-dark border border-twitch-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-twitch-purple'
