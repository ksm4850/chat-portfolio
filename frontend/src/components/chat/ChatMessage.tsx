import { ChevronRight, CircleAlert, FileText, Info, Sparkles } from 'lucide-react'
import { memo, useState } from 'react'
import { usePortfolio } from '@/lib/queries'
import { navigate, runTool } from '@/lib/tools'
import type { Portfolio, Source } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useChat, type ChatAction, type MessagePart } from '@/store/chat'

const VIEW_LABELS: Record<string, string> = { home: '홈', career: '경력', skills: '기술 스택' }

function actionLabel(a: ChatAction, portfolio: Portfolio | null) {
  if (a.tool === 'navigate') {
    if (a.args.view !== 'project') return `${VIEW_LABELS[a.args.view as string] ?? a.args.view} 열기`
    const p = portfolio?.projects.find((p) => p.id === a.args.projectId)
    const tab = p?.tabs.find((t) => t.id === a.args.tab) ?? p?.tabs[0]
    return `${p?.title ?? a.args.projectId} › ${tab?.label ?? a.args.tab ?? ''} 열기`
  }
  if (a.tool === 'highlight') {
    const quote = a.args.quote as string | undefined
    return quote ? `“${quote.length > 30 ? `${quote.slice(0, 30)}…` : quote}” 강조` : '관련 부분 강조'
  }
  return a.tool
}

async function openSource(s: Source) {
  if (!s.location) return
  await navigate({ view: 'project', projectId: s.location.projectId, tab: s.location.tab })
  await runTool('highlight', { anchor: s.location.anchor })
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1 py-2" aria-label="응답 중">
      {[0, 150, 300].map((d) => (
        <span key={d} className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60" style={{ animationDelay: `${d}ms` }} />
      ))}
    </span>
  )
}

const SourceList = memo(function SourceList({ sources, shownAnchors }: { sources: Source[]; shownAnchors: string }) {
  const [open, setOpen] = useState(false)
  const shown = new Set(shownAnchors.split(' '))
  return (
    <div className="text-xs text-muted-foreground">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 transition hover:bg-muted hover:text-foreground"
        aria-expanded={open}
      >
        <ChevronRight className={cn('size-3 transition-transform', open && 'rotate-90')} />
        검색된 자료 {sources.length}건
      </button>
      {open && (
        <div className="mt-1 space-y-0.5 border-l pl-2 animate-in fade-in slide-in-from-top-1 duration-150">
          {sources.map((s) => {
            const isShown = !!s.location && shown.has(s.location.anchor)
            return (
              <button
                key={s.location?.anchor ?? s.title}
                type="button"
                disabled={!s.location}
                title={s.snippet}
                onClick={() => openSource(s)}
                className={cn(
                  'flex w-full items-center gap-2 rounded px-1.5 py-1 text-left transition enabled:hover:bg-muted disabled:cursor-default',
                  !isShown && 'opacity-60',
                )}
              >
                <FileText className="size-3 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{s.title}</span>
                {isShown && <span className="shrink-0 rounded bg-amber-50 px-1 text-[10px] text-amber-700">화면에 표시함</span>}
                <span className="shrink-0 tabular-nums">{s.score.toFixed(2)}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
})

const TextPart = memo(function TextPart({ text }: { text: string }) {
  return <span>{text}</span>
})

type Segment = { kind: 'text'; text: string } | { kind: 'link'; text: string; actionIds: string[] }

/** 텍스트 끝의 마지막 문장을 떼어 낸다: [앞부분, 마지막 문장, 끝 공백] */
function splitLastSentence(text: string): [string, string, string] {
  const body = text.replace(/\s+$/, '')
  const trailing = text.slice(body.length)
  let cut = 0
  for (const m of body.matchAll(/[.!?](?=\s)|\n/g)) if (m.index + 1 < body.length) cut = m.index + 1
  const lead = body.slice(cut).match(/^\s*/)![0].length
  return [body.slice(0, cut + lead), body.slice(cut + lead), trailing]
}

/** 위치 표시가 붙은 문장을 링크로 만든다. 같은 표시에서 나온 액션(navigate + highlight)은 한 링크로 묶는다. */
function toSegments(parts: MessagePart[]): Segment[] {
  const out: Segment[] = []
  for (const part of parts) {
    if (part.kind === 'text') {
      out.push({ kind: 'text', text: part.text })
      continue
    }
    const last = out.at(-1)
    if (last?.kind === 'link') {
      last.actionIds.push(part.actionId)
    } else if (last?.kind === 'text') {
      out.pop()
      const [head, sentence, trailing] = splitLastSentence(last.text)
      if (head) out.push({ kind: 'text', text: head })
      out.push({ kind: 'link', text: sentence, actionIds: [part.actionId] })
      if (trailing) out.push({ kind: 'text', text: trailing })
    } else {
      out.push({ kind: 'link', text: '화면 보기', actionIds: [part.actionId] })
    }
  }
  return out.reduce<Segment[]>((merged, seg) => {
    const prev = merged.at(-1)
    if (seg.kind === 'text' && prev?.kind === 'text') prev.text += seg.text
    else merged.push(seg)
    return merged
  }, [])
}

const LinkedSentence = memo(function LinkedSentence({
  messageId,
  actionId,
  text,
  title,
  active,
  failed,
}: {
  messageId: string
  actionId: string
  text: string
  title: string
  active: boolean
  failed: boolean
}) {
  const replay = useChat((s) => s.replay)
  return (
    <span
      role="button"
      tabIndex={0}
      title={title}
      onClick={() => replay(messageId, actionId)}
      onKeyDown={(e) => e.key === 'Enter' && replay(messageId, actionId)}
      className={cn(
        'cursor-pointer rounded-[3px] underline decoration-dotted decoration-1 underline-offset-[5px] transition-colors duration-500 box-decoration-clone hover:decoration-foreground',
        active ? 'bg-amber-100 decoration-amber-500' : 'decoration-muted-foreground/60',
        failed && 'decoration-destructive/60',
      )}
    >
      {text}
    </span>
  )
})

export const ChatMessage = memo(function ChatMessage({ id }: { id: string }) {
  const message = useChat((s) => s.messagesById[id])
  const activeActionId = useChat((s) => (s.activeAction?.messageId === id ? s.activeAction.actionId : null))
  const { data: portfolio } = usePortfolio()
  if (!message) return null

  if (message.role === 'user') {
    return (
      <div className="flex justify-end animate-in fade-in slide-in-from-bottom-1">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm whitespace-pre-wrap text-primary-foreground">
          {message.text}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-2.5 animate-in fade-in slide-in-from-bottom-1">
      <div className="flex size-7 shrink-0 items-center justify-center rounded-full border">
        <Sparkles className="size-3.5" />
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        {/* LLM 답변은 자료를 따로 보여 주지 않는다. 검색 모드에서는 자료 목록이 답이다. */}
        {message.notice && message.sources.length > 0 && (
          <SourceList
            sources={message.sources}
            shownAnchors={message.actions
              .filter((a) => a.tool === 'highlight' && a.status === 'done')
              .map((a) => a.args.anchor)
              .join(' ')}
          />
        )}

        {message.parts.length > 0 ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {toSegments(message.parts).map((seg, i) => {
              if (seg.kind === 'text') return <TextPart key={i} text={seg.text} />
              const actions = seg.actionIds.map((id) => message.actions.find((a) => a.id === id)).filter((a) => !!a)
              const primary = actions.findLast((a) => a.tool === 'highlight') ?? actions.at(-1)
              if (!primary) return <TextPart key={i} text={seg.text} />
              return (
                <LinkedSentence
                  key={primary.id}
                  messageId={message.id}
                  actionId={primary.id}
                  text={seg.text}
                  title={actions.map((a) => actionLabel(a, portfolio)).join(' · ')}
                  active={!!activeActionId && seg.actionIds.includes(activeActionId)}
                  failed={actions.every((a) => a.status === 'error')}
                />
              )
            })}
          </p>
        ) : (
          message.streaming && !message.error && <TypingDots />
        )}
        {message.notice && !message.streaming && !message.error && (
          <p className="flex gap-1.5 rounded-md bg-amber-50 px-2.5 py-2 text-xs leading-relaxed text-amber-800">
            <Info className="mt-0.5 size-3.5 shrink-0" />
            {message.notice}
          </p>
        )}
        {message.error && (
          <p className="flex gap-1.5 text-sm text-destructive">
            <CircleAlert className="mt-0.5 size-4 shrink-0" />
            {message.error}
          </p>
        )}
      </div>
    </div>
  )
})
