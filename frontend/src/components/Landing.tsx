import { ArrowRight } from 'lucide-react'
import { Composer } from '@/components/Composer'
import { Button } from '@/components/ui/button'
import { track } from '@/lib/analytics'
import { HEADLINE_LINES } from '@/lib/profile'
import { SUGGESTIONS } from '@/lib/suggestions'
import { useChat } from '@/store/chat'
import { useUi } from '@/store/ui'

export function Landing() {
  const ask = useChat((s) => s.ask)
  const openApp = useUi((s) => s.openApp)

  const start = (question: string, method: 'typed' | 'suggestion') => {
    track('ask_question', { ask_method: method, ask_location: 'landing' })
    openApp({ chat: true })
    void ask(question)
  }

  return (
    <main className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-10">
      <div className="w-full max-w-2xl animate-in fade-in slide-in-from-bottom-1 duration-300">
        <div className="mb-8 text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            AI가 포트폴리오를 안내합니다
          </span>
          <h1 className="mt-4 text-xl font-bold tracking-tight break-keep sm:text-3xl md:text-4xl">
            {HEADLINE_LINES.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
          </h1>
          <p className="mt-3 text-muted-foreground">궁금한 점을 물어보시면 답변과 함께 관련 화면을 바로 보여 드립니다.</p>
        </div>

        <Composer size="lg" autoFocus onSubmit={(q) => start(q, 'typed')} placeholder="예) 자기소개 부탁드립니다" />

        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <Button key={s} variant="outline" size="sm" className="rounded-full text-muted-foreground" onClick={() => start(s, 'suggestion')}>
              {s}
            </Button>
          ))}
        </div>

        <div className="mt-10 text-center">
          <Button variant="link" className="text-muted-foreground" onClick={() => openApp({ chat: false })}>
            채팅 없이 직접 둘러보기
            <ArrowRight data-icon="inline-end" />
          </Button>
        </div>
      </div>
    </main>
  )
}
