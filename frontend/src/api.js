const BASE = import.meta.env.VITE_API_URL || ''

function headers() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
  }
}

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: headers(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || res.statusText)
  return data
}

export const api = {
  get:  (path)       => req('GET', path),
  post: (path, body) => req('POST', path, body),
}
