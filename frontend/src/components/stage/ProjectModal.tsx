import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ProjectView } from '@/components/stage/views'
import { Button } from '@/components/ui/button'
import { markActivity } from '@/lib/attention'
import { usePortfolio } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { useUi, type ProjectRef } from '@/store/ui'

/** 스테이지 영역 안에만 뜨는 모달. 채팅 패널은 가리지 않아 대화하면서 화면 변화를 볼 수 있다. */
export function ProjectModal() {
  const project = useUi((s) => s.project)
  const closeProject = useUi((s) => s.closeProject)
  const { data: portfolio } = usePortfolio()
  const [shown, setShown] = useState<ProjectRef | null>(project)
  const [closing, setClosing] = useState(false)

  if (project && project !== shown) {
    setShown(project)
    setClosing(false)
  }
  if (!project && shown && !closing) setClosing(true)

  useEffect(() => {
    if (!project) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closeProject()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [project, closeProject])

  if (!shown) return null
  const summary = portfolio?.projects.find((p) => p.id === shown.projectId)

  return (
    <div className="absolute inset-0 z-30">
      <div
        aria-hidden
        onClick={closeProject}
        className={cn(
          'absolute inset-0 bg-black/25 backdrop-blur-[2px] fill-mode-forwards',
          closing ? 'animate-out fade-out duration-200' : 'animate-in fade-in duration-300',
        )}
      />
      <div
        role="dialog"
        aria-label={summary?.title}
        onAnimationEnd={(e) => {
          if (closing && e.target === e.currentTarget) {
            setShown(null)
            setClosing(false)
          }
        }}
        className={cn(
          'absolute inset-3 mx-auto flex max-w-4xl flex-col overflow-hidden rounded-2xl border bg-background shadow-2xl fill-mode-forwards md:inset-6',
          closing
            ? 'animate-out fade-out zoom-out-95 slide-out-to-bottom-4 duration-200 ease-in'
            : 'animate-in fade-in zoom-in-95 slide-in-from-bottom-6 duration-300 ease-out',
        )}
      >
        <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b px-4 md:px-6">
          <span className="truncate text-sm text-muted-foreground">
            {summary ? `${summary.company} · ${summary.period}` : ''}
          </span>
          <Button variant="ghost" size="icon-sm" onClick={closeProject} aria-label="닫기">
            <X />
          </Button>
        </div>
        <div
          data-stage
          onWheel={markActivity}
          onTouchMove={markActivity}
          onPointerDown={markActivity}
          className="min-h-0 flex-1 overflow-y-auto"
        >
          <ProjectView key={shown.projectId} project={shown} />
        </div>
      </div>
    </div>
  )
}
