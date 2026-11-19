import { Sparkles } from 'lucide-react'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { EventLog } from '@/components/EventLog'
import { Header } from '@/components/Header'
import { Landing } from '@/components/Landing'
import { ProjectModal } from '@/components/stage/ProjectModal'
import { Sidebar } from '@/components/stage/Sidebar'
import { CareerView, HomeView, SkillsView } from '@/components/stage/views'
import { Button } from '@/components/ui/button'
import { TooltipProvider } from '@/components/ui/tooltip'
import { markActivity } from '@/lib/attention'
import { useUi } from '@/store/ui'

function Stage() {
  const page = useUi((s) => s.page)
  switch (page.name) {
    case 'home':
      return <HomeView />
    case 'career':
      return <CareerView />
    case 'skills':
      return <SkillsView />
  }
}

function Workspace() {
  const chatOpen = useUi((s) => s.chatOpen)
  const setChatOpen = useUi((s) => s.setChatOpen)
  return (
    <div className="relative flex min-h-0 flex-1">
      <Sidebar />
      <div className="relative min-w-0 flex-1">
        <main data-stage onWheel={markActivity} onTouchMove={markActivity} onPointerDown={markActivity} className="h-full overflow-y-auto">
          <Stage />
        </main>
        <ProjectModal />
      </div>
      {chatOpen ? (
        <ChatPanel />
      ) : (
        <Button size="lg" className="absolute right-6 bottom-6 z-40 h-11 rounded-full px-4 shadow-lg" onClick={() => setChatOpen(true)}>
          <Sparkles data-icon="inline-start" />
          AI에게 물어보기
        </Button>
      )}
    </div>
  )
}

export default function App() {
  const screen = useUi((s) => s.screen)
  return (
    <TooltipProvider>
      <div className="flex h-dvh flex-col">
        <Header />
        {screen === 'landing' ? <Landing /> : <Workspace />}
        <EventLog />
      </div>
    </TooltipProvider>
  )
}
