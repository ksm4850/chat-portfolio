import { Briefcase, FileText, Folder, House, Layers, type LucideIcon } from 'lucide-react'
import { navigate } from '@/lib/tools'
import { usePortfolio } from '@/lib/queries'
import { cn } from '@/lib/utils'
import { useUi } from '@/store/ui'

type ItemProps = { active?: boolean; icon: LucideIcon; label: string; onClick?: () => void }

function Item({ active, icon: Icon, label, onClick }: ItemProps) {
  if (!onClick) {
    return (
      <div title={label} className="flex w-full cursor-default items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-muted-foreground/70">
        <Icon className="size-4 shrink-0" />
        <span className="truncate">{label}</span>
      </div>
    )
  }
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        'flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm transition',
        active ? 'bg-accent font-medium text-accent-foreground' : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
      )}
    >
      <Icon className="size-4 shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  )
}

export function Sidebar() {
  const page = useUi((s) => s.page)
  const openProjectId = useUi((s) => s.project?.projectId)
  const { data } = usePortfolio()

  return (
    <nav className="hidden w-60 shrink-0 flex-col gap-1 overflow-y-auto border-r p-3 lg:flex">
      <Item active={!openProjectId && page.name === 'home'} icon={House} label="홈" onClick={() => navigate({ view: 'home' })} />
      <Item active={!openProjectId && page.name === 'career'} icon={Briefcase} label="경력" onClick={() => navigate({ view: 'career' })} />
      <Item active={!openProjectId && page.name === 'skills'} icon={Layers} label="기술 스택" onClick={() => navigate({ view: 'skills' })} />
      {data?.careers.map((c) => (
        <div key={c.company} className="mt-4 flex flex-col gap-1">
          <div className="px-2.5 pb-1 text-xs font-medium text-muted-foreground">{c.company}</div>
          {c.projectIds.map((id) => {
            const p = data.projects.find((p) => p.id === id)
            if (!p) return null
            if (p.tabs.length === 0) return <Item key={id} icon={FileText} label={p.title} />
            return (
              <Item
                key={id}
                active={openProjectId === id}
                icon={Folder}
                label={p.title}
                onClick={() => navigate({ view: 'project', projectId: id })}
              />
            )
          })}
        </div>
      ))}
    </nav>
  )
}
