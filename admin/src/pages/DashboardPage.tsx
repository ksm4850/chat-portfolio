import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { PageHeader } from '@/components/PageHeader'
import { api } from '@/lib/api'
import { toastError } from '@/lib/errors'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { GuideLog, GuideStats, Usage } from '@/lib/types'

const PERIODS = [7, 30, 90]

const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone

const seconds = (value: number | null) => (value === null ? '–' : `${(value / 1000).toFixed(1)}s`)

const percent = (part: number, total: number) => (total === 0 ? '–' : `${Math.round((part / total) * 100)}%`)

const shortDate = (value: string) => value.slice(5).replace('-', '/')

const logsLink = (question: string) => `/logs?${new URLSearchParams({ q: question.trim() })}`

export function DashboardPage() {
  const [days, setDays] = useState(7)
  const [stats, setStats] = useState<GuideStats | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [recent, setRecent] = useState<GuideLog[] | null>(null)

  const load = useCallback(() => {
    api.guideStats(days, TZ).then(setStats).catch(toastError)
    api.usage().then(setUsage).catch(toastError)
    api.listGuideLogs({}, 0, 10).then((page) => setRecent(page.items)).catch(toastError)
  }, [days])

  useEffect(() => {
    load()
  }, [load])

  const summary = stats?.summary

  return (
    <div className="mx-auto grid max-w-6xl gap-4 p-6">
      <PageHeader
        title="대시보드"
        description={`방문자 안내 질문 기준, ${TZ} 날짜로 센다.`}
        actions={
          <>
            <div className="flex rounded-md border p-0.5">
              {PERIODS.map((period) => (
                <Button
                  key={period}
                  variant={period === days ? 'secondary' : 'ghost'}
                  size="xs"
                  onClick={() => setDays(period)}
                >
                  {period}일
                </Button>
              ))}
            </div>
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw /> 새로고침
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="질문" value={summary?.questions} />
        <StatTile label="방문자" value={summary?.visitors} />
        <StatTile label="대화" value={summary?.threads} />
        <StatTile
          label="오늘 LLM 호출"
          value={usage?.llmCallsToday}
          suffix={usage && ` / ${usage.llmCallsPerDay.toLocaleString()}`}
        >
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{
                width: `${usage ? Math.min(1, usage.llmCallsToday / Math.max(1, usage.llmCallsPerDay)) * 100 : 0}%`,
              }}
            />
          </div>
        </StatTile>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>일별 질문</CardTitle>
          <CardDescription>막대에 올리면 그날 질문·방문자 수를 보여 준다.</CardDescription>
        </CardHeader>
        <CardContent>{stats ? <DailyChart daily={stats.daily} /> : <Skeleton className="h-48" />}</CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>응답 성능</CardTitle>
            <CardDescription>첫 토큰은 LLM 답변만 잰다. 끊김은 방문자가 답변 도중 나간 경우.</CardDescription>
          </CardHeader>
          <CardContent>
            {summary ? (
              <dl className="grid grid-cols-3 gap-y-3 text-sm">
                <dt className="text-muted-foreground" />
                <dt className="text-right text-xs text-muted-foreground">평균</dt>
                <dt className="text-right text-xs text-muted-foreground">p95</dt>
                <dt className="text-muted-foreground">첫 토큰</dt>
                <dd className="text-right tabular-nums">{seconds(summary.latency.firstTokenAvgMs)}</dd>
                <dd className="text-right tabular-nums">{seconds(summary.latency.firstTokenP95Ms)}</dd>
                <dt className="text-muted-foreground">전체 응답</dt>
                <dd className="text-right tabular-nums">{seconds(summary.latency.totalAvgMs)}</dd>
                <dd className="text-right tabular-nums">{seconds(summary.latency.totalP95Ms)}</dd>
                <dt className="text-muted-foreground">끊김</dt>
                <dd className="col-span-2 text-right tabular-nums">
                  {summary.incomplete.toLocaleString()}건 ({percent(summary.incomplete, summary.questions)})
                </dd>
              </dl>
            ) : (
              <Skeleton className="h-28" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>답변 모드</CardTitle>
            <CardDescription>llm 이 아니면 LLM 없이 검색 결과로 답한 것(한도 초과·실패·꺼짐).</CardDescription>
          </CardHeader>
          <CardContent>
            {stats ? (
              <ShareList
                items={stats.modes.map((m) => ({ key: m.mode, label: m.mode, count: m.count }))}
                total={stats.summary.questions}
              />
            ) : (
              <Skeleton className="h-28" />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>자주 나온 질문</CardTitle>
            <CardDescription>대소문자·앞뒤 공백만 다른 질문은 하나로 센다. 누르면 대화 로그에서 찾는다.</CardDescription>
          </CardHeader>
          <CardContent>
            {stats ? (
              <QuestionList
                items={stats.topQuestions.map((q) => ({ key: q.question, question: q.question, meta: `${q.count}회` }))}
              />
            ) : (
              <Skeleton className="h-40" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>최근 질문</CardTitle>
            <CardDescription>
              기간과 상관없이 최근 10건. <Link to="/logs" className="underline underline-offset-2">전체 보기</Link>
            </CardDescription>
          </CardHeader>
          <CardContent>
            {recent ? (
              <QuestionList
                items={recent.map((log) => ({
                  key: log.id,
                  question: log.question,
                  meta: formatDateTime(log.createdAt),
                  dimmed: !log.completed,
                }))}
              />
            ) : (
              <Skeleton className="h-40" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function StatTile({
  label,
  value,
  suffix,
  children,
}: {
  label: string
  value: number | undefined
  suffix?: ReactNode
  children?: ReactNode
}) {
  return (
    <Card className="gap-1 py-4">
      <CardContent className="px-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">
          {value?.toLocaleString() ?? '–'}
          {suffix && <span className="text-sm font-normal text-muted-foreground">{suffix}</span>}
        </div>
        {children}
      </CardContent>
    </Card>
  )
}

function DailyChart({ daily }: { daily: GuideStats['daily'] }) {
  const max = Math.max(1, ...daily.map((d) => d.questions))
  const ticks = new Set([0, Math.floor((daily.length - 1) / 2), daily.length - 1])

  return (
    <div className="grid gap-1 pt-4">
      <div className="relative h-48">
        <div className="pointer-events-none absolute inset-x-0 top-0 border-t border-dashed border-border" />
        <span className="pointer-events-none absolute top-0 left-0 -translate-y-full pb-0.5 text-xs text-muted-foreground tabular-nums">
          {max.toLocaleString()}
        </span>
        <div className="flex h-full items-end gap-0.5 border-b border-border">
          {daily.map((d) => (
            <Tooltip key={d.date}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="group flex h-full min-w-0 flex-1 items-end"
                  aria-label={`${d.date} 질문 ${d.questions}건, 방문자 ${d.visitors}명`}
                >
                  <div
                    className="w-full rounded-t-[4px] bg-primary/80 group-hover:bg-primary"
                    style={{ height: `${(d.questions / max) * 100}%` }}
                  />
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <div className="font-medium">{d.date}</div>
                <div className="tabular-nums">
                  질문 {d.questions.toLocaleString()}건 · 방문자 {d.visitors.toLocaleString()}명
                </div>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      </div>
      <div className="flex gap-0.5 text-xs text-muted-foreground tabular-nums">
        {daily.map((d, i) => (
          <span key={d.date} className="min-w-0 flex-1 text-center whitespace-nowrap">
            {ticks.has(i) ? shortDate(d.date) : ''}
          </span>
        ))}
      </div>
    </div>
  )
}

function ShareList({ items, total }: { items: { key: string; label: string; count: number }[]; total: number }) {
  if (items.length === 0) return <Empty />
  return (
    <ul className="grid gap-3 text-sm">
      {items.map((item) => (
        <li key={item.key} className="grid gap-1">
          <div className="flex justify-between">
            <span>{item.label}</span>
            <span className="text-muted-foreground tabular-nums">
              {item.count.toLocaleString()}건 · {percent(item.count, total)}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${(item.count / Math.max(1, total)) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

function QuestionList({
  items,
}: {
  items: { key: string; question: string; meta: string; dimmed?: boolean }[]
}) {
  if (items.length === 0) return <Empty />
  return (
    <ul className="grid text-sm">
      {items.map((item) => (
        <li key={item.key}>
          <Link
            to={logsLink(item.question)}
            className="flex gap-3 rounded-md px-2 py-1.5 hover:bg-muted"
          >
            <span className={cn('min-w-0 flex-1 truncate', item.dimmed && 'text-muted-foreground')}>
              {item.question}
            </span>
            <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{item.meta}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Empty() {
  return <p className="py-6 text-center text-sm text-muted-foreground">기록이 없다.</p>
}
