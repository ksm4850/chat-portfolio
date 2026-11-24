import { LayoutGrid, MessageCircle, Terminal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { navigate } from '@/lib/tools'
import { useChat } from '@/store/chat'
import { useUi } from '@/store/ui'

const DEBUG = new URLSearchParams(location.search).has('debug')

export function Header() {
  const { screen, chatOpen, logOpen, openApp, showLanding, toggleLog } = useUi()
  const hasMessages = useChat((s) => s.messageIds.length > 0)
  const value = screen === 'landing' || chatOpen ? 'chat' : 'browse'

  const onModeChange = (next: string) => {
    if (next === 'browse') return openApp({ chat: false })
    if (hasMessages) openApp({ chat: true })
    else showLanding()
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b px-4 md:px-6">
      <button
        type="button"
        onClick={() => void navigate({ view: 'home' })}
        className="flex items-center gap-2"
      >
        <span className="text-sm font-semibold">김상명 Portfolio</span>
      </button>

      <div className="flex items-center gap-2">
        {DEBUG && (
          <Button variant={logOpen ? 'secondary' : 'outline'} size="lg" onClick={toggleLog}>
            <Terminal data-icon="inline-start" />
            <span className="hidden sm:inline">이벤트 로그</span>
          </Button>
        )}
        <Tabs value={value} onValueChange={onModeChange}>
          <TabsList>
            <TabsTrigger value="chat">
              <MessageCircle />
              대화로 보기
            </TabsTrigger>
            <TabsTrigger value="browse">
              <LayoutGrid />
              직접 보기
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </header>
  )
}
