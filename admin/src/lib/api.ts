import { useAuth } from '@/store/auth'
import type {
  Character,
  CharacterInput,
  DocumentDetail,
  DocumentInput,
  GuideLogPage,
  GuideLogQuery,
  GuideStats,
  IngestResult,
  KnowledgeDocument,
  ReplyContext,
  SearchHit,
  SourceFile,
  SourceFileContent,
  TokenResponse,
  Usage,
} from '@/lib/types'

const BASE = '/api/v1'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function toError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  const error = body?.error
  return new ApiError(
    response.status,
    error?.code ?? 'http_error',
    error?.message ?? `요청이 실패했다 (${response.status})`,
  )
}

let refreshing: Promise<boolean> | null = null

// 동시에 여러 요청이 401 을 받아도 refresh 는 한 번만 한다. refresh 토큰은 쓰면 폐기된다(RTR).
function refreshTokens(): Promise<boolean> {
  refreshing ??= (async () => {
    const { refreshToken, setTokens, clear } = useAuth.getState()
    if (!refreshToken) return false
    const response = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!response.ok) {
      clear()
      return false
    }
    const tokens: TokenResponse = await response.json()
    setTokens(tokens.access_token, tokens.refresh_token)
    return true
  })().finally(() => {
    refreshing = null
  })
  return refreshing
}

export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const send = () => {
    const headers = new Headers(init.headers)
    const token = useAuth.getState().accessToken
    if (token) headers.set('Authorization', `Bearer ${token}`)
    if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    return fetch(`${BASE}${path}`, { ...init, headers })
  }
  let response = await send()
  if (response.status === 401 && (await refreshTokens())) response = await send()
  if (response.status === 401) useAuth.getState().clear()
  if (!response.ok) throw await toError(response)
  return response
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authorizedFetch(path, init)
  return response.status === 204 ? (undefined as T) : response.json()
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) })

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    body: new URLSearchParams({ username: email, password }),
  })
  if (!response.ok) throw await toError(response)
  const tokens: TokenResponse = await response.json()
  const me = await fetch(`${BASE}/users/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  })
  const user = me.ok ? await me.json() : null
  if (!user?.isSuperuser) throw new ApiError(403, 'forbidden', '관리자 계정이 아니다.')
  useAuth.getState().setTokens(tokens.access_token, tokens.refresh_token, email)
}

export async function logout(): Promise<void> {
  const { refreshToken, clear } = useAuth.getState()
  clear()
  if (refreshToken) {
    await fetch(`${BASE}/auth/logout`, json('POST', { refresh_token: refreshToken })).catch(() => {})
  }
}

const characters = (id: string) => `/admin/characters/${id}`

export const api = {
  listCharacters: () => request<Character[]>('/admin/characters'),
  getCharacter: (id: string) => request<Character>(characters(id)),
  createCharacter: (input: CharacterInput) =>
    request<Character>('/admin/characters', json('POST', input)),
  updateCharacter: (id: string, input: Partial<CharacterInput>) =>
    request<Character>(characters(id), json('PATCH', input)),
  deleteCharacter: (id: string) => request<void>(characters(id), { method: 'DELETE' }),

  listDocuments: (id: string) => request<KnowledgeDocument[]>(`${characters(id)}/documents`),
  getDocument: (id: string, documentId: string) =>
    request<DocumentDetail>(`${characters(id)}/documents/${documentId}`),
  addDocument: (id: string, input: DocumentInput) =>
    request<KnowledgeDocument>(`${characters(id)}/documents`, json('POST', input)),
  updateDocument: (id: string, documentId: string, input: Partial<DocumentInput>) =>
    request<KnowledgeDocument>(`${characters(id)}/documents/${documentId}`, json('PATCH', input)),
  deleteDocument: (id: string, documentId: string) =>
    request<void>(`${characters(id)}/documents/${documentId}`, { method: 'DELETE' }),
  search: (id: string, query: string, limit: number) =>
    request<SearchHit[]>(`${characters(id)}/search`, json('POST', { query, limit })),

  listSourceFiles: () => request<SourceFile[]>('/admin/portfolio/files'),
  getSourceFile: (file: string) =>
    request<SourceFileContent>(`/admin/portfolio/files/${encodeURIComponent(file)}`),
  saveSourceFile: (file: string, content: string) =>
    request<IngestResult>(`/admin/portfolio/files/${encodeURIComponent(file)}`, json('PUT', { content })),
  reingest: () => request<IngestResult>('/admin/portfolio/ingest', { method: 'POST' }),

  usage: () => request<Usage>('/admin/usage'),

  listGuideLogs: (query: GuideLogQuery, offset: number, limit: number) => {
    const params = new URLSearchParams({ offset: String(offset), limit: String(limit) })
    for (const [key, value] of Object.entries(query)) if (value) params.set(key, value)
    return request<GuideLogPage>(`/admin/guide/logs?${params}`)
  },
  guideStats: (days: number, tz: string) =>
    request<GuideStats>(`/admin/guide/stats?${new URLSearchParams({ days: String(days), tz })}`),

  createChatSession: (characterId: string) =>
    request<{ sessionId: string }>('/admin/chat/sessions', json('POST', { characterId })),
}

export type ChatEvent =
  | { type: 'context'; data: ReplyContext }
  | { type: 'delta'; data: { text: string } }
  | { type: 'done' }
  | { type: 'error'; data: { code: string; message: string } }

export async function* streamTestReply(
  sessionId: string,
  text: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await authorizedFetch(`/admin/chat/sessions/${sessionId}/messages`, {
    ...json('POST', { text }),
    signal,
  })
  const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value
    let end: number
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      const name = block.match(/^event: (.*)$/m)?.[1]
      const data = block.match(/^data: (.*)$/m)?.[1]
      if (name) yield { type: name, data: data ? JSON.parse(data) : undefined } as ChatEvent
    }
  }
}
