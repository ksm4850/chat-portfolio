import { memo, useEffect, useRef } from 'react'
import { useChat, type LoggedEvent } from '@/store/chat'
import { useUi } from '@/store/ui'

const colorOf = (type: string) =>
  type.startsWith('TOOL_CALL')
    ? 'text-sky-400'
    : type.startsWith('TEXT_MESSAGE')
      ? 'text-emerald-400'
      : type === 'CUSTOM'
        ? 'text-amber-400'
        : type === 'RUN_ERROR'
          ? 'text-red-400'
          : 'text-fuchsia-400'

const time = (at: number) => new Date(at).toTimeString().slice(0, 8) + '.' + String(at % 1000).padStart(3, '0')

export function EventLog() {
  const logOpen = useUi((s) => s.logOpen)
  return logOpen ? <EventLogPanel /> : null
}

function EventLogPanel() {
  const toggleLog = useUi((s) => s.toggleLog)
  const clearEvents = useChat((s) => s.clearEvents)

  return (
    <section className="flex h-64 shrink-0 flex-col border-t border-zinc-800 bg-zinc-950 text-zinc-300">
      <div className="flex h-9 shrink-0 items-center justify-between border-b border-zinc-800 px-4 text-xs">
        <span className="font-medium text-zinc-100">
          AG-UI 이벤트 스트림 <EventCount />
        </span>
        <div className="flex gap-1">
          <button type="button" onClick={clearEvents} className="rounded px-2 py-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100">
            지우기
          </button>
          <button type="button" onClick={toggleLog} className="rounded px-2 py-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100">
            닫기
          </button>
        </div>
      </div>
      <EventRows />
    </section>
  )
}

function EventCount() {
  const count = useChat((s) => s.events.length)
  return <span className="text-zinc-500">({count})</span>
}

function EventRows() {
  const events = useChat((s) => s.events)
  const bodyRef = useRef<HTMLPreElement>(null)

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight })
  }, [events])

  return (
    <pre ref={bodyRef} className="min-h-0 flex-1 overflow-y-auto p-3 font-mono text-xs leading-5 break-all whitespace-pre-wrap">
      {events.length === 0 && <span className="text-zinc-600">질문을 보내면 서버가 보낸 이벤트가 여기에 표시됩니다.</span>}
      {events.map((entry, i) => (
        <EventRow key={i} entry={entry} />
      ))}
    </pre>
  )
}

const CATEGORY: Record<string, { label: string; className: string }> = {
  call: { label: '호출', className: 'bg-sky-500/15 text-sky-300' },
  source: { label: '참고', className: 'bg-amber-500/15 text-amber-300' },
  text: { label: '텍스트', className: 'bg-emerald-500/10 text-emerald-300/80' },
  state: { label: '상태', className: 'bg-zinc-500/15 text-zinc-400' },
}

const categoryOf = (event: { type: string; name?: unknown }) =>
  event.type.startsWith('TOOL_CALL')
    ? CATEGORY.call
    : event.type === 'CUSTOM' && event.name === 'sources'
      ? CATEGORY.source
      : event.type.startsWith('TEXT_MESSAGE')
        ? CATEGORY.text
        : CATEGORY.state

const EventRow = memo(function EventRow({ entry }: { entry: LoggedEvent }) {
  const { type, ...rest } = entry.event as { type: string; name?: unknown } & Record<string, unknown>
  delete rest.rawEvent
  const category = categoryOf({ type, name: rest.name })
  return (
    <>
      {type === 'RUN_STARTED' && <div className="my-2 border-t border-dashed border-zinc-700 pt-1 text-zinc-500">새 질문</div>}
      <div>
        <span className="text-zinc-600">{time(entry.at)}</span>{' '}
        <span className={`inline-block w-12 rounded px-1 text-center ${category.className}`}>{category.label}</span>{' '}
        <span className={colorOf(type)}>{type.padEnd(21)}</span>
        {JSON.stringify(rest)}
      </div>
    </>
  )
})
