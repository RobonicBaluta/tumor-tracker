// Fetch helpers compartidos por todos los componentes para llamar al backend.
// Unifica la URL base y el parseo de errores.

// Lee VITE_API_BASE en build (Vercel), fallback a localhost en dev.
export const API_BASE: string =
  (import.meta as any).env?.VITE_API_BASE || 'http://localhost:5000'

export async function apiGet<T = any>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = params
    ? '?' + new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== '' && v !== null)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : ''
  const res = await fetch(`${API_BASE}${path}${qs}`)
  const data = await res.json().catch(() => ({}))
  if (!res.ok || (data && (data as any).error)) {
    throw new Error((data as any)?.error || `HTTP ${res.status}`)
  }
  return data as T
}

export async function apiPost<T = any>(path: string, body: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || (data && (data as any).error)) {
    throw new Error((data as any)?.error || `HTTP ${res.status}`)
  }
  return data as T
}

export async function apiDelete<T = any>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || (data && (data as any).error)) {
    throw new Error((data as any)?.error || `HTTP ${res.status}`)
  }
  return data as T
}
