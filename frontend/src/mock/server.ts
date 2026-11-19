import catalog from '@content/portfolio/projects.json'
import { collapseWhitespace, normalizeQuote, stripMarkdown } from '@/lib/text'
import type { Portfolio, ProjectDetail, Section, Source } from '@/lib/types'
import { createMarkerParser, llmDeltas, mockAnswer } from '@/mock/llm'

const markdownFiles = import.meta.glob<string>('../../../content/portfolio/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

const readMarkdown = (file: string) => {
  const entry = Object.entries(markdownFiles).find(([path]) => path.endsWith(`/${file}`))
  if (!entry) throw new Error(`md 없음: ${file}`)
  return entry[1]
}

/** contracts/README.md 1장 "섹션 분할과 anchor 규칙" 구현 */
export function splitSections(md: string, projectId: string, tabId: string): Section[] {
  const lines = md.split('\n')
  const raw: { level: number; title: string; body: string[] }[] = []
  let docTitle = ''
  let inFence = false
  let current: (typeof raw)[number] | null = null

  for (const line of lines) {
    if (line.trimStart().startsWith('```')) inFence = !inFence
    const heading = !inFence && /^(#{1,3}) (.+)$/.exec(line)
    if (heading && heading[1].length === 1 && !docTitle && !current) {
      docTitle = heading[2].trim()
      current = { level: 1, title: docTitle, body: [] }
      continue
    }
    if (heading && heading[1].length >= 2) {
      if (current) raw.push(current)
      current = { level: heading[1].length, title: heading[2].trim(), body: [] }
      continue
    }
    current?.body.push(line)
  }
  if (current) raw.push(current)

  return raw
    .map((s) => ({ ...s, text: s.body.join('\n').trim() }))
    .filter((s) => s.level > 1 || s.text)
    .map((s, i) => ({ anchor: `${projectId}-${tabId}-${i + 1}`, level: s.level, title: s.title, body: s.text }))
}

const projects: ProjectDetail[] = catalog.projects.map((p) => ({
  ...p,
  url: 'url' in p ? (p.url as string) : null,
  tabs: p.tabs.map((t) => ({ id: t.id, label: t.label, sections: splitSections(readMarkdown(t.file), p.id, t.id) })),
}))

const portfolio: Portfolio = {
  profile: catalog.profile,
  careers: catalog.careers,
  skills: catalog.skills,
  projects: projects.map((p) => ({ ...p, tabs: p.tabs.map(({ id, label }) => ({ id, label })) })),
}

const sectionIndex = new Map(
  projects.flatMap((p) =>
    p.tabs.flatMap((t) =>
      t.sections.map((s) => [s.anchor, { projectId: p.id, tab: t.id, plain: collapseWhitespace(stripMarkdown(s.body)) }] as const),
    ),
  ),
)

const bigrams = (text: string) => {
  const s = text.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')
  return new Set(Array.from({ length: Math.max(s.length - 1, 0) }, (_, i) => s.slice(i, i + 2)))
}

const overlap = (q: Set<string>, text: string) => {
  const t = bigrams(text)
  let hit = 0
  for (const g of q) if (t.has(g)) hit++
  return hit
}

/** 섹션에서 질문과 가장 많이 겹치는 줄을 quote로 고른다 (80자 이하). */
function bestQuote(q: Set<string>, body: string) {
  const lines = stripMarkdown(body)
    .split('\n')
    .map(collapseWhitespace)
    .filter((l) => l.length >= 8)
  const best = lines.sort((a, b) => overlap(q, b) - overlap(q, a))[0]
  return best?.slice(0, 80)
}

type MockSource = Source & { quote?: string }

const publicSources = (sources: MockSource[]): Source[] =>
  sources.map((s) => ({ title: s.title, snippet: s.snippet, score: s.score, location: s.location }))

function search(question: string): MockSource[] {
  const q = bigrams(question)
  if (!q.size) return []
  const scored = projects.flatMap((p) =>
    p.tabs.flatMap((t) =>
      t.sections
        .filter((s) => s.body)
        .map((s) => {
          const title = bigrams(`${p.title} ${t.label} ${s.title}`)
          const body = bigrams(s.body)
          let hit = 0
          for (const g of q) hit += (title.has(g) ? 0.6 : 0) + (body.has(g) ? 0.4 : 0)
          return {
            title: `${p.title} - ${t.label} > ${s.title}`,
            snippet: collapseWhitespace(stripMarkdown(s.body)).slice(0, 120),
            score: Math.min(1, hit / q.size),
            location: { projectId: p.id, tab: t.id, anchor: s.anchor },
            quote: bestQuote(q, s.body),
          }
        }),
    ),
  )
  return scored.sort((a, b) => b.score - a.score).slice(0, 3)
}

const MIN_SCORE = 0.3
const MIN_SOURCE_SCORE = 0.12
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const id = (prefix: string) => `${prefix}_${crypto.randomUUID().slice(0, 8)}`

type RunInput = { threadId: string; runId: string; messages: { role: string; content: string }[] }
type Emit = (event: Record<string, unknown>, delayMs?: number) => Promise<void>

function toolCaller(emit: Emit, messageId: string) {
  let lastLocation = ''
  async function call(name: string, args: Record<string, unknown>) {
    const toolCallId = id('call')
    const json = JSON.stringify(args)
    await emit({ type: 'TOOL_CALL_START', toolCallId, toolCallName: name, parentMessageId: messageId })
    for (let i = 0; i < json.length; i += 24) await emit({ type: 'TOOL_CALL_ARGS', toolCallId, delta: json.slice(i, i + 24) })
    await emit({ type: 'TOOL_CALL_END', toolCallId })
  }
  /** contracts/README.md 5장: anchor·quote 검증 후, 위치가 바뀌었을 때만 navigate를 보낸다. */
  return async function show(anchor: string, quote?: string) {
    const section = sectionIndex.get(anchor)
    if (!section) return console.warn('[mock] 없는 anchor를 버림:', anchor)
    const validQuote = quote && section.plain.includes(normalizeQuote(quote)) ? quote : undefined
    if (quote && !validQuote) console.warn('[mock] 섹션에 없는 quote를 버림:', quote)
    const location = `${section.projectId}:${section.tab}`
    if (location !== lastLocation) {
      lastLocation = location
      await call('navigate', { view: 'project', projectId: section.projectId, tab: section.tab })
    }
    await call('highlight', validQuote ? { anchor, quote: validQuote } : { anchor })
  }
}

async function runLlm(input: RunInput, emit: Emit) {
  const question = input.messages.findLast((m) => m.role === 'user')?.content ?? ''
  const sources = search(question).filter((s) => s.score >= MIN_SOURCE_SCORE)
  const messageId = id('msg')
  const show = toolCaller(emit, messageId)
  const parser = createMarkerParser()

  await emit({ type: 'CUSTOM', name: 'mode', value: 'llm' })
  await emit({ type: 'CUSTOM', name: 'sources', value: publicSources(sources) }, 500)
  await emit({ type: 'TEXT_MESSAGE_START', messageId, role: 'assistant' })
  for (const delta of [...llmDeltas(mockAnswer(question, sources)), null]) {
    const pieces = delta === null ? parser.flush() : parser.feed(delta)
    for (const piece of pieces) {
      if (piece.kind === 'text') await emit({ type: 'TEXT_MESSAGE_CONTENT', messageId, delta: piece.text }, 28)
      else await show(piece.anchor, piece.quote)
    }
  }
  await emit({ type: 'TEXT_MESSAGE_END', messageId })
}

async function runFallback(input: RunInput, emit: Emit) {
  const question = input.messages.findLast((m) => m.role === 'user')?.content ?? ''
  const sources = search(question).filter((s) => s.score >= MIN_SOURCE_SCORE)
  const top = sources[0]
  const acting = top && top.score >= MIN_SCORE && top.location
  const messageId = id('msg')
  const sectionTitle = top?.title.split(' > ').at(-1)
  const text = acting
    ? `관련 내용을 찾았습니다. '${sectionTitle}' 부분을 열어 드리겠습니다.`
    : sources.length
      ? '딱 맞는 내용은 찾지 못했지만 관련 있어 보이는 자료를 모았습니다.'
      : '관련 자료를 찾지 못했습니다. 다른 표현으로 물어봐 주십시오.'

  await emit({ type: 'CUSTOM', name: 'mode', value: 'fallback' })
  await emit({ type: 'CUSTOM', name: 'sources', value: publicSources(sources) })
  await emit({ type: 'TEXT_MESSAGE_START', messageId, role: 'assistant' })
  for (const delta of text.match(/.{1,8}/gsu) ?? []) await emit({ type: 'TEXT_MESSAGE_CONTENT', messageId, delta }, 30)
  await emit({ type: 'TEXT_MESSAGE_END', messageId })
  if (acting && top.location) await toolCaller(emit, messageId)(top.location.anchor, top.quote)
}

function sseResponse(input: RunInput) {
  const encoder = new TextEncoder()
  const fallback = new URLSearchParams(location.search).get('mode') === 'fallback'
  const body = new ReadableStream({
    async start(controller) {
      const emit: Emit = async (event, delayMs = 15) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
        await sleep(delayMs)
      }
      await sleep(300)
      await emit({ type: 'RUN_STARTED', threadId: input.threadId, runId: input.runId })
      await (fallback ? runFallback : runLlm)(input, emit)
      await emit({ type: 'RUN_FINISHED', threadId: input.threadId, runId: input.runId })
      controller.close()
    },
  })
  return new Response(body, { headers: { 'Content-Type': 'text/event-stream' } })
}

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

export function installMockServer() {
  const realFetch = window.fetch.bind(window)
  window.fetch = async (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input), location.origin)
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
    if (!url.pathname.startsWith('/api/v1/')) return realFetch(input, init)
    await sleep(120)

    if (method === 'POST' && url.pathname === '/api/v1/visitors') {
      return json({ visitorToken: 'mock-token', expiresAt: new Date(Date.now() + 86_400_000).toISOString() }, 201)
    }
    if (method === 'GET' && url.pathname === '/api/v1/portfolio') return json(portfolio)
    const projectMatch = /^\/api\/v1\/portfolio\/projects\/([^/]+)$/.exec(url.pathname)
    if (method === 'GET' && projectMatch) {
      const project = projects.find((p) => p.id === decodeURIComponent(projectMatch[1]))
      return project ? json(project) : json({ code: 'not_found' }, 404)
    }
    if (method === 'POST' && url.pathname === '/api/v1/agui/run') {
      const body = init?.body ?? (input instanceof Request ? await input.text() : '{}')
      return sseResponse(JSON.parse(String(body)))
    }
    return json({ code: 'not_found' }, 404)
  }
  console.info('[mock] /api/v1 요청을 mock 서버가 처리합니다 (?mode=fallback 으로 폴백 경로 확인)')
}
