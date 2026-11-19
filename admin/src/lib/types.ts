export type ExampleDialogue = { user: string; assistant: string }

export type Character = {
  id: string
  slug: string
  name: string
  greeting: string
  profile: string
  speakingStyle: string
  exampleDialogues: ExampleDialogue[]
  isPublic: boolean
  createdAt: string
  updatedAt: string
}

export type CharacterInput = Omit<Character, 'id' | 'createdAt' | 'updatedAt'>

export type KnowledgeDocument = {
  id: string
  title: string
  source: string
  chunkCount: number
  createdAt: string
  updatedAt: string
}

export type Chunk = {
  position: number
  content: string
  meta: Record<string, unknown> | null
}

export type DocumentDetail = KnowledgeDocument & { content: string; chunks: Chunk[] }

export type DocumentInput = { title: string; source: string; content: string }

export type SearchHit = {
  documentId: string
  title: string
  content: string
  score: number
  meta: Record<string, unknown> | null
}

export type SourceFile = {
  file: string
  source: string
  projectId: string
  projectTitle: string
  tabId: string
  tabLabel: string
}

export type SourceFileContent = SourceFile & { content: string }

export type IngestResult = { projects: number; documents: number; sections: number; chunks: number }

export type Usage = { llmCallsToday: number; llmCallsPerDay: number }

export type ReplyContext = { memories: SearchHit[]; systemPrompt: string }

export type TokenResponse = { access_token: string; refresh_token: string; expires_in: number }

export type GuideLog = {
  id: string
  createdAt: string
  visitorId: string
  threadId: string | null
  gaClientId: string | null
  question: string
  answer: string
  mode: string
  scores: number[]
  anchors: string[]
  firstTokenMs: number | null
  totalMs: number
  completed: boolean
  inputTokens: number | null
  outputTokens: number | null
  reasoningTokens: number | null
  cachedTokens: number | null
  traceId: string | null
}

export type GuideLogPage = { items: GuideLog[]; totalCount: number; offset: number; limit: number }

export type GuideLogQuery = { q?: string; visitorId?: string; gaClientId?: string; threadId?: string }

export type GuideStats = {
  since: string
  until: string
  tz: string
  summary: {
    questions: number
    visitors: number
    threads: number
    incomplete: number
    latency: {
      firstTokenAvgMs: number | null
      firstTokenP95Ms: number | null
      totalAvgMs: number | null
      totalP95Ms: number | null
    }
  }
  daily: { date: string; questions: number; visitors: number }[]
  modes: { mode: string; count: number }[]
  topQuestions: { question: string; count: number }[]
}
