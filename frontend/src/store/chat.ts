import { HttpAgent } from '@ag-ui/client'
import { EventType, type AGUIEvent, type BaseEvent } from '@ag-ui/core'
import { create } from 'zustand'
import { gaClientId } from '@/lib/analytics'
import { getVisitorToken } from '@/lib/api'
import { waitForIdle } from '@/lib/attention'
import { capabilities, runTool } from '@/lib/tools'
import type { Source } from '@/lib/types'

export type ChatAction = {
  id: string
  tool: string
  args: Record<string, unknown>
  /** 이 액션이 도착했을 때까지 나온 답변 글자 수. 읽기 속도 기준 실행 시점과 문장 링크 묶음에 쓴다. */
  offset: number
  status: 'queued' | 'running' | 'done' | 'error'
  error?: string
}

export type MessagePart = { kind: 'text'; text: string } | { kind: 'action'; actionId: string }

export type ChatMessage =
  | { id: string; role: 'user'; text: string }
  | {
      id: string
      role: 'assistant'
      parts: MessagePart[]
      streaming: boolean
      sources: Source[]
      actions: ChatAction[]
      error?: string
      /** 검색 모드로 답했을 때 답변 아래에 붙이는 안내 */
      notice?: string
    }

type AssistantMessage = Extract<ChatMessage, { role: 'assistant' }>

export type LoggedEvent = { at: number; event: BaseEvent }

type ChatState = {
  messageIds: string[]
  messagesById: Record<string, ChatMessage>
  events: LoggedEvent[]
  mode: 'llm' | 'fallback' | null
  busy: boolean
  activeAction: { messageId: string; actionId: string } | null
  ask: (question: string) => Promise<void>
  replay: (messageId: string, actionId: string) => Promise<void>
  clearEvents: () => void
}

const uid = (prefix: string) => `${prefix}_${crypto.randomUUID().slice(0, 8)}`

const agent = new HttpAgent({ url: '/api/v1/agui/run', threadId: uid('thread') })

/** 사용자가 읽는 속도(초당 글자 수)와 형광펜 사이 최소 간격 */
const READ_CHARS_PER_SEC = 8
const MIN_HIGHLIGHT_GAP_MS = 2500

const FALLBACK_NOTICE =
  '지금은 AI 답변을 쓸 수 없어 관련 자료 위치만 안내해 드렸습니다. 이용량이 많거나 일시적인 문제일 수 있으니 잠시 후 다시 질문해 주십시오.'

// 서버 error.code 별 안내. 없는 code 는 상태 코드로 고른다.
const ERROR_MESSAGES: Record<string, string> = {
  visitor_daily_limit: '하루에 질문할 수 있는 횟수를 모두 쓰셨습니다. 내일 다시 질문해 주십시오.',
  ip_hourly_limit: '같은 네트워크에서 질문이 많이 들어오고 있습니다. 한 시간쯤 뒤에 다시 질문해 주십시오.',
  chat_too_fast: '질문을 너무 빠르게 보내셨습니다. 몇 초 뒤에 다시 보내 주십시오.',
  message_too_long: '질문이 너무 깁니다. 500자 이내로 줄여서 보내 주십시오.',
}

function errorMessage(e: unknown): string {
  const { status, payload } = e as { status?: number; payload?: { error?: { code?: string } } }
  const code = payload?.error?.code
  if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code]
  return status === 429
    ? '요청이 많아 잠시 후 다시 시도해 주십시오.'
    : '응답을 받지 못했습니다. 잠시 후 다시 시도해 주십시오.'
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const autoCancelled = new Set<string>()

export const useChat = create<ChatState>((set, get) => {
  const patchAssistant = (id: string, patch: (m: AssistantMessage) => Partial<AssistantMessage>) =>
    set((s) => {
      const m = s.messagesById[id]
      if (m?.role !== 'assistant') return {}
      return { messagesById: { ...s.messagesById, [id]: { ...m, ...patch(m) } } }
    })

  const patchAction = (messageId: string, actionId: string, patch: Partial<ChatAction>) =>
    patchAssistant(messageId, (m) => ({
      actions: m.actions.map((a) => (a.id === actionId ? { ...a, ...patch } : a)),
    }))

  async function execute(messageId: string, action: ChatAction) {
    patchAction(messageId, action.id, { status: 'running' })
    set({ activeAction: { messageId, actionId: action.id } })
    try {
      await runTool(action.tool, action.args)
      patchAction(messageId, action.id, { status: 'done' })
    } catch (e) {
      console.warn('[tool]', action.tool, e)
      patchAction(messageId, action.id, { status: 'error', error: (e as Error).message })
    }
  }

  /** 첫 표시의 액션은 바로, 이후 표시는 추정 읽기 위치가 그 문장에 닿고 직전 형광펜 뒤 최소 간격이 지난 뒤 실행한다. 같은 표시에서 나온 액션은 이어서 실행한다. */
  function createPacer(messageId: string) {
    let textStartedAt: number | null = null
    let lastHighlightAt = 0
    let lastOffset: number | null = null
    let queue = Promise.resolve()
    const cancelled = () => autoCancelled.has(messageId)

    return {
      textStarted() {
        textStartedAt ??= performance.now()
      },
      enqueue(action: ChatAction) {
        queue = queue.then(async () => {
          if (cancelled()) return
          if (lastOffset !== null && action.offset !== lastOffset) {
            const readAt = (textStartedAt ?? performance.now()) + (action.offset / READ_CHARS_PER_SEC) * 1000
            const gapAt = action.tool === 'highlight' ? lastHighlightAt + MIN_HIGHLIGHT_GAP_MS : 0
            const wait = Math.max(readAt, gapAt) - performance.now()
            if (wait > 0) await sleep(wait)
            await waitForIdle(cancelled)
            if (cancelled()) return
          }
          lastOffset = action.offset
          await execute(messageId, action)
          if (action.tool === 'highlight') lastHighlightAt = performance.now()
        })
      },
    }
  }

  async function runOnce(assistantId: string, refreshToken: boolean) {
    agent.headers = { 'X-Visitor-Token': await getVisitorToken({ refresh: refreshToken }) }
    const pendingCalls = new Map<string, { name: string; args: string }>()
    const pacer = createPacer(assistantId)
    let textLength = 0
    let pendingText = ''
    let pendingEvents: LoggedEvent[] = []
    let frame: number | null = null

    // 글자 조각과 로그 이벤트를 모아 화면 프레임마다 한 번만 store에 반영한다.
    const flush = () => {
      if (frame !== null) cancelAnimationFrame(frame)
      frame = null
      if (pendingText) {
        const text = pendingText
        pendingText = ''
        patchAssistant(assistantId, (m) => {
          const last = m.parts.at(-1)
          return last?.kind === 'text'
            ? { parts: [...m.parts.slice(0, -1), { kind: 'text', text: last.text + text }] }
            : { parts: [...m.parts, { kind: 'text', text }] }
        })
      }
      if (pendingEvents.length) {
        const logged = pendingEvents
        pendingEvents = []
        set((s) => ({ events: [...s.events, ...logged] }))
      }
    }
    const scheduleFlush = () => {
      if (frame === null) frame = requestAnimationFrame(flush)
    }

    await agent.runAgent(
      { runId: uid('run'), forwardedProps: { capabilities, gaClientId: await gaClientId() } },
      {
        onEvent: ({ event }) => {
          pendingEvents.push({ at: Date.now(), event })
          const e = event as AGUIEvent
          if (e.type !== EventType.TEXT_MESSAGE_CONTENT && e.type !== EventType.TOOL_CALL_ARGS) flush()
          switch (e.type) {
            case EventType.CUSTOM:
              if (e.name === 'mode') {
                set({ mode: e.value as ChatState['mode'] })
                if (e.value === 'fallback') patchAssistant(assistantId, () => ({ notice: FALLBACK_NOTICE }))
              }
              if (e.name === 'sources') patchAssistant(assistantId, () => ({ sources: e.value as Source[] }))
              break
            case EventType.TEXT_MESSAGE_CONTENT:
              pacer.textStarted()
              textLength += e.delta.length
              pendingText += e.delta
              scheduleFlush()
              break
            case EventType.TEXT_MESSAGE_END:
              patchAssistant(assistantId, () => ({ streaming: false }))
              break
            case EventType.TOOL_CALL_START:
              pendingCalls.set(e.toolCallId, { name: e.toolCallName, args: '' })
              break
            case EventType.TOOL_CALL_ARGS: {
              const call = pendingCalls.get(e.toolCallId)
              if (call) call.args += e.delta
              scheduleFlush()
              break
            }
            case EventType.TOOL_CALL_END: {
              const call = pendingCalls.get(e.toolCallId)
              if (!call) break
              pendingCalls.delete(e.toolCallId)
              let args: Record<string, unknown> = {}
              let parseError: string | undefined
              try {
                args = JSON.parse(call.args || '{}')
              } catch {
                parseError = '인자 JSON 파싱 실패'
              }
              const action: ChatAction = {
                id: e.toolCallId,
                tool: call.name,
                args,
                offset: textLength,
                status: parseError ? 'error' : 'queued',
                error: parseError,
              }
              patchAssistant(assistantId, (m) => ({
                actions: [...m.actions, action],
                parts: [...m.parts, { kind: 'action', actionId: action.id }],
              }))
              if (!parseError) pacer.enqueue(action)
              break
            }
            case EventType.RUN_ERROR:
              patchAssistant(assistantId, () => ({ error: e.message, streaming: false }))
              break
          }
        },
      },
    ).finally(flush)
  }

  return {
    messageIds: [],
    messagesById: {},
    events: [],
    mode: null,
    busy: false,
    activeAction: null,

    ask: async (question) => {
      const text = question.trim()
      if (!text || get().busy) return
      const userId = uid('user')
      const assistantId = uid('assistant')
      get().messageIds.forEach((id) => autoCancelled.add(id))
      set((s) => ({
        busy: true,
        activeAction: null,
        messageIds: [...s.messageIds, userId, assistantId],
        messagesById: {
          ...s.messagesById,
          [userId]: { id: userId, role: 'user', text },
          [assistantId]: { id: assistantId, role: 'assistant', parts: [], streaming: true, sources: [], actions: [] },
        },
      }))
      agent.addMessage({ id: uid('msg'), role: 'user', content: text })
      try {
        await runOnce(assistantId, false).catch((e: Error) => {
          if (/401/.test(e.message)) return runOnce(assistantId, true)
          throw e
        })
      } catch (e) {
        const message = errorMessage(e)
        console.error('[agent]', e)
        patchAssistant(assistantId, () => ({ error: message }))
      } finally {
        patchAssistant(assistantId, () => ({ streaming: false }))
        set({ busy: false })
      }
    },

    replay: async (messageId, actionId) => {
      const msg = get().messagesById[messageId]
      if (!msg || msg.role !== 'assistant') return
      autoCancelled.add(messageId)
      const index = msg.actions.findIndex((a) => a.id === actionId)
      const target = msg.actions[index]
      const lastNavigate = msg.actions.slice(0, index + 1).findLast((a) => a.tool === 'navigate')
      set({ activeAction: { messageId, actionId } })
      if (lastNavigate) await runTool(lastNavigate.tool, lastNavigate.args).catch(() => {})
      if (target.tool !== 'navigate') await runTool(target.tool, target.args).catch(() => {})
    },

    clearEvents: () => set({ events: [] }),
  }
})
