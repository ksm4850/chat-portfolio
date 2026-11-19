import { useEffect, useRef, useState } from 'react'
import { RotateCcw, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { HitList } from '@/components/character/SearchPanel'
import { api, streamTestReply } from '@/lib/api'
import { toastError } from '@/lib/errors'
import type { Character, ReplyContext } from '@/lib/types'

type Turn = {
  question: string
  answer: string
  context: ReplyContext | null
  error: string | null
  streaming: boolean
}

export function ChatTestPanel({ character }: { character: Character }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const session = useRef<string | null>(null)
  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const streaming = turns.at(-1)?.streaming ?? false

  useEffect(() => () => abort.current?.abort(), [])
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [turns])

  const update = (patch: (turn: Turn) => Partial<Turn>) =>
    setTurns((all) => all.map((turn, i) => (i === all.length - 1 ? { ...turn, ...patch(turn) } : turn)))

  function reset() {
    abort.current?.abort()
    session.current = null
    setTurns([])
  }

  async function send() {
    const question = text.trim()
    if (!question || streaming) return
    setText('')
    setTurns((all) => [...all, { question, answer: '', context: null, error: null, streaming: true }])
    abort.current = new AbortController()
    try {
      session.current ??= (await api.createChatSession(character.id)).sessionId
      for await (const event of streamTestReply(session.current, question, abort.current.signal)) {
        if (event.type === 'context') update(() => ({ context: event.data }))
        else if (event.type === 'delta') update((turn) => ({ answer: turn.answer + event.data.text }))
        else if (event.type === 'error') update(() => ({ error: event.data.message }))
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError')) {
        update(() => ({ error: e instanceof Error ? e.message : '응답을 받지 못했다.' }))
        toastError(e)
      }
    } finally {
      update(() => ({ streaming: false }))
    }
  }

  return (
    <div className="grid gap-4">
      <div className="flex items-center gap-2">
        <p className="flex-1 text-xs text-muted-foreground">
          저장된 설정·지식으로 답한다. 비공개여도 되고 사용량 제한에 잡히지 않는다. 설정을 바꾸면 새 대화로 확인한다.
        </p>
        <Button variant="outline" size="sm" onClick={reset} disabled={turns.length === 0}>
          <RotateCcw /> 새 대화
        </Button>
      </div>

      <div className="grid gap-4">
        {turns.length === 0 && character.greeting && (
          <Bubble role="assistant">{character.greeting}</Bubble>
        )}
        {turns.map((turn, index) => (
          <div key={index} className="grid gap-2">
            <Bubble role="user">{turn.question}</Bubble>
            <Bubble role="assistant">
              {turn.answer || (turn.streaming ? '…' : '')}
              {turn.error && <span className="mt-1 block text-destructive">{turn.error}</span>}
            </Bubble>
            {turn.context && (
              <div className="ml-2 grid gap-1 text-sm">
                <details>
                  <summary className="cursor-pointer text-xs text-muted-foreground">
                    검색된 기억 {turn.context.memories.length}개
                  </summary>
                  <div className="mt-2">
                    <HitList hits={turn.context.memories} />
                  </div>
                </details>
                <details>
                  <summary className="cursor-pointer text-xs text-muted-foreground">시스템 프롬프트</summary>
                  <pre className="mt-2 max-h-96 overflow-y-auto rounded-lg bg-muted p-3 font-mono text-xs whitespace-pre-wrap">
                    {turn.context.systemPrompt}
                  </pre>
                </details>
              </div>
            )}
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form
        className="sticky bottom-0 flex gap-2 bg-background py-2"
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
      >
        <Textarea
          rows={2}
          maxLength={2000}
          placeholder="질문을 입력 (Enter 전송, Shift+Enter 줄바꿈)"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              send()
            }
          }}
        />
        <Button type="submit" disabled={streaming || !text.trim()} className="self-end">
          <Send /> 전송
        </Button>
      </form>
    </div>
  )
}

function Bubble({ role, children }: { role: 'user' | 'assistant'; children: React.ReactNode }) {
  return (
    <div
      className={
        role === 'user'
          ? 'max-w-[80%] justify-self-end rounded-2xl bg-primary px-3.5 py-2 text-sm whitespace-pre-wrap text-primary-foreground'
          : 'max-w-[80%] justify-self-start rounded-2xl bg-muted px-3.5 py-2 text-sm whitespace-pre-wrap'
      }
    >
      {children}
    </div>
  )
}
