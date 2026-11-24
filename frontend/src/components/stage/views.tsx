import { ArrowRight, ChevronRight, ExternalLink } from 'lucide-react'
import type { ReactNode } from 'react'
import { Markdown } from '@/components/Markdown'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toPublicUrl } from '@/lib/media'
import { usePortfolio, useProject } from '@/lib/queries'
import { HEADLINE_LINES, ROLE } from '@/lib/profile'
import { navigate } from '@/lib/tools'
import type { ProjectSummary, Section } from '@/lib/types'
import { cn } from '@/lib/utils'
import { viewKey, type ProjectRef, type View } from '@/store/ui'

function ViewRoot({ view, ready, wide, children }: { view: View; ready: boolean; wide?: boolean; children: ReactNode }) {
  return (
    <div
      data-view-key={viewKey(view)}
      data-ready={ready}
      className={cn('mx-auto p-6 animate-in fade-in duration-300 md:p-10', wide ? 'max-w-5xl' : 'max-w-3xl')}
    >
      {children}
    </div>
  )
}

function Loading() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}

const hasDocs = (p: ProjectSummary) => p.tabs.length > 0

function ProjectCard({ p }: { p: ProjectSummary }) {
  if (!hasDocs(p)) {
    return (
      <div className="flex items-center justify-between gap-4 rounded-xl border border-dashed px-5 py-4 text-sm">
        <h3 className="font-medium text-muted-foreground">{p.title}</h3>
        <span className="shrink-0 text-xs text-muted-foreground">{p.period}</span>
      </div>
    )
  }
  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => navigate({ view: 'project', projectId: p.id })}
      onKeyDown={(e) => e.key === 'Enter' && navigate({ view: 'project', projectId: p.id })}
      className="group cursor-pointer transition hover:ring-foreground/20 hover:shadow-md"
    >
      <CardContent className="flex items-center gap-6">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="font-semibold">{p.title}</h3>
            <span className="text-xs text-muted-foreground">{p.period}</span>
          </div>
          {p.summary && <p className="mt-1.5 line-clamp-2 text-sm text-muted-foreground">{p.summary}</p>}
          <div className="mt-3 flex flex-wrap gap-1">
            {p.stacks.slice(0, 6).map((s) => (
              <Badge key={s} variant="outline">
                {s}
              </Badge>
            ))}
          </div>
        </div>
        <ArrowRight className="size-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-foreground" />
      </CardContent>
    </Card>
  )
}

export function HomeView() {
  const { data } = usePortfolio()
  return (
    <ViewRoot view={{ name: 'home' }} ready={!!data}>
      {!data ? (
        <Loading />
      ) : (
        <>
          <p className="text-sm text-muted-foreground">{ROLE}</p>
          <h1 className="mt-1 text-xl font-bold tracking-tight break-keep sm:text-2xl md:text-3xl">
            {HEADLINE_LINES.map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
          </h1>
          <p className="mt-3 text-muted-foreground">
            Python·Go 기반 백엔드와 AWS 인프라를 설계하고 운영합니다. 프로젝트를 직접 둘러보시거나, 궁금한 점은 채팅으로 편하게 물어봐 주세요.
          </p>
          {data.careers.map((c) => (
            <section key={c.company} className="mt-12">
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-3">
                <div>
                  <h2 className="text-lg font-semibold">{c.company}</h2>
                  <p className="mt-0.5 text-sm text-muted-foreground">{c.description}</p>
                </div>
                <span className="text-sm text-muted-foreground">{c.period}</span>
              </div>
              <div className="mt-4 flex flex-col gap-3">
                {c.projectIds.map((id) => {
                  const p = data.projects.find((p) => p.id === id)
                  return p && <ProjectCard key={id} p={p} />
                })}
              </div>
            </section>
          ))}
        </>
      )}
    </ViewRoot>
  )
}

export function CareerView() {
  const { data } = usePortfolio()
  return (
    <ViewRoot view={{ name: 'career' }} ready={!!data}>
      <h1 className="text-2xl font-bold tracking-tight">경력</h1>
      {!data ? (
        <div className="mt-8">
          <Loading />
        </div>
      ) : (
        <ol className="mt-8 space-y-8 border-l pl-6">
          {data.careers.map((c) => (
            <li key={c.company} className="relative">
              <span className="absolute top-1.5 -left-[29px] size-2.5 rounded-full border-2 border-background bg-foreground" />
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-semibold">{c.company}</h3>
                <span className="text-sm text-muted-foreground">{c.period}</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{c.description}</p>
              <div className="mt-2 flex gap-1">
                {c.roles.map((r) => (
                  <Badge key={r} variant="secondary">
                    {r}
                  </Badge>
                ))}
              </div>
              <div className="mt-3 grid gap-2">
                {c.projectIds.map((id) => {
                  const p = data.projects.find((p) => p.id === id)
                  if (p && !hasDocs(p)) {
                    return (
                      <div key={id} className="rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
                        {p.title}
                      </div>
                    )
                  }
                  return (
                    p && (
                      <button
                        key={id}
                        type="button"
                        onClick={() => navigate({ view: 'project', projectId: id })}
                        className="flex items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition hover:bg-accent"
                      >
                        <span>{p.title}</span>
                        <ChevronRight className="size-4 text-muted-foreground" />
                      </button>
                    )
                  )
                })}
              </div>
            </li>
          ))}
        </ol>
      )}
    </ViewRoot>
  )
}

export function SkillsView() {
  const { data } = usePortfolio()
  return (
    <ViewRoot view={{ name: 'skills' }} ready={!!data}>
      <h1 className="text-2xl font-bold tracking-tight">기술 스택</h1>
      <div className="mt-8 space-y-4">
        {data?.skills.map((g) => (
          <Card key={g.category}>
            <CardContent>
              <h3 className="text-sm font-medium text-muted-foreground">{g.category}</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {g.items.map((s) => (
                  <Badge key={s} variant="outline" className="h-7 px-2.5 text-sm">
                    {s}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )) ?? <Loading />}
      </div>
    </ViewRoot>
  )
}

function SectionBlock({ section }: { section: Section }) {
  const Heading = section.level <= 2 ? 'h2' : 'h3'
  return (
    <section data-anchor={section.anchor} className="scroll-mt-6 rounded-xl p-1">
      <Heading className={cn('font-semibold tracking-tight', section.level <= 2 ? 'mt-8 text-xl' : 'mt-6 text-lg')}>
        {section.title}
      </Heading>
      {section.body && (
        <div className="mt-3">
          <Markdown>{section.body}</Markdown>
        </div>
      )}
    </section>
  )
}

export function ProjectView({ project: ref }: { project: ProjectRef }) {
  const view: View = { name: 'project', ...ref }
  const { data: project, error } = useProject(ref.projectId)
  const tab = project?.tabs.find((t) => t.id === ref.tab) ?? project?.tabs[0]

  return (
    <ViewRoot view={view} ready={!!project}>
      {error && <p className="text-sm text-destructive">프로젝트를 불러오지 못했습니다.</p>}
      {!project ? (
        !error && <Loading />
      ) : (
        <>
          <h1 className="text-2xl font-bold tracking-tight">{project.title}</h1>
          {project.url && (
            <a
              href={project.url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              서비스 바로가기 <ExternalLink className="size-3.5" />
            </a>
          )}
          <p className="mt-4 text-muted-foreground">{project.summary}</p>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {project.stacks.map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </div>

          {project.media.length > 0 && (
            <div className="mt-6 flex snap-x gap-3 overflow-x-auto pb-2">
              {project.media.map((m) => (
                <a key={m} href={toPublicUrl(m)} target="_blank" rel="noreferrer" className="shrink-0 snap-start">
                  <img src={toPublicUrl(m)} alt="" loading="lazy" className="h-44 w-auto rounded-lg border object-cover" />
                </a>
              ))}
            </div>
          )}

          {tab && project.tabs.length > 1 && (
            <Tabs
              value={tab.id}
              onValueChange={(t) => navigate({ view: 'project', projectId: project.id, tab: t })}
              className="mt-8"
            >
              <TabsList className="h-auto flex-wrap">
                {project.tabs.map((t) => (
                  <TabsTrigger key={t.id} value={t.id}>
                    {t.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          )}

          {tab && (
            <div
              key={tab.id}
              className={cn('border-t animate-in fade-in slide-in-from-bottom-1 duration-300', project.tabs.length > 1 ? 'mt-4' : 'mt-8')}
            >
              {tab.sections.map((s) => (
                <SectionBlock key={s.anchor} section={s} />
              ))}
            </div>
          )}
        </>
      )}
    </ViewRoot>
  )
}
