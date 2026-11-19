import type { Portfolio, ProjectDetail } from '@/lib/types'

const TOKEN_KEY = 'visitorToken'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) throw new ApiError(res.status, `${init?.method ?? 'GET'} ${url} → ${res.status}`)
  return res.json() as Promise<T>
}

export const fetchPortfolio = () => getJson<Portfolio>('/api/v1/portfolio')

export const fetchProject = (projectId: string) =>
  getJson<ProjectDetail>(`/api/v1/portfolio/projects/${encodeURIComponent(projectId)}`)

type StoredToken = { visitorToken: string; expiresAt: string }

export async function getVisitorToken({ refresh = false } = {}): Promise<string> {
  const raw = localStorage.getItem(TOKEN_KEY)
  if (raw && !refresh) {
    const stored = JSON.parse(raw) as StoredToken
    if (new Date(stored.expiresAt).getTime() - Date.now() > 60_000) return stored.visitorToken
  }
  const issued = await getJson<StoredToken>('/api/v1/visitors', { method: 'POST' })
  localStorage.setItem(TOKEN_KEY, JSON.stringify(issued))
  return issued.visitorToken
}
