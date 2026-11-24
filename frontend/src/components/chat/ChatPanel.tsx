import { PanelRightClose, Sparkles } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef } from 'react'
import { ChatMessage } from '@/components/chat/ChatMessage'
import { Composer } from '@/components/Composer'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SUGGESTIONS } from '@/lib/suggestions'
import { useChat } from '@/store/chat'
import { useUi } from '@/store/ui'

const MODE_BADGE = {
  llm: { label: 'LLM', className: 'bg-emerald-50 text-emerald-700' },
  fallback: { label: '검색 모드', className: 'bg-amber-50 text-amber-700' },
}

export function ChatPanel() {
  const messageIds = useChat((s) => s.messageIds)
  const busy = useChat((s) => s.busy)
  const mode = useChat((s) => s.mode)
  const ask = useChat((s) => s.ask)
  const setChatOpen = useUi((s) => s.setChatOpen)
  const listRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)
  const hasMessages = messageIds.length > 0

  useLayoutEffect(() => {
    stickToBottom.current = true
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messageIds])

  // 스트리밍 중에는 이 컴포넌트가 다시 렌더링되지 않으므로, 내용 높이 변화로 바닥 고정을 유지한다.
  useEffect(() => {
    const list = listRef.current
    const content = contentRef.current
    if (!list || !content) return
    const observer = new ResizeObserver(() => {
      if (stickToBottom.current) list.scrollTop = list.scrollHeight
    })
    observer.observe(content)
    return () => observer.disconnect()
  }, [hasMessages])

  const onScroll = () => {
    const list = listRef.current
    if (list) stickToBottom.current = list.scrollHeight - list.scrollTop - list.clientHeight < 48
  }

  return (
    <aside className="fixed inset-0 z-30 flex flex-col bg-background md:static md:z-auto md:w-[400px] md:shrink-0 md:border-l">
      <div className="flex h-12 shrink-0 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Sparkles className="size-4" />
          AI 안내
          {mode && <Badge className={MODE_BADGE[mode].className}>{MODE_BADGE[mode].label}</Badge>}
        </div>
        <Button variant="ghost" size="icon-sm" onClick={() => setChatOpen(false)} aria-label="채팅 닫기">
          <PanelRightClose />
        </Button>
      </div>

      <div ref={listRef} onScroll={onScroll} className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
        {hasMessages ? (
          <div ref={contentRef} className="space-y-5">
            {messageIds.map((id) => (
              <ChatMessage key={id} id={id} />
            ))}
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted-foreground">
            <Sparkles className="mb-3 size-6" />
            <p>
              프로젝트, 경력, 기술에 대해 편하게 물어봐 주세요.
              <br />
              답변과 함께 관련 화면을 열어 드립니다.
            </p>
          </div>
        )}
      </div>

      <div className="shrink-0 border-t p-3">
        {!hasMessages && (
          <div className="mb-2 flex gap-1.5 overflow-x-auto pb-1">
            {SUGGESTIONS.map((s) => (
              <Button key={s} variant="outline" size="xs" className="shrink-0 rounded-full text-muted-foreground" onClick={() => ask(s)}>
                {s}
              </Button>
            ))}
          </div>
        )}
        <Composer onSubmit={ask} disabled={busy} />
      </div>
    </aside>
  )
}
