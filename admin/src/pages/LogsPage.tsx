import { Fragment, useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { ChevronLeft, ChevronRight, RefreshCw, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { PageHeader } from '@/components/PageHeader'
import { api } from '@/lib/api'
import { toastError } from '@/lib/errors'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { GuideLog, GuideLogPage, GuideLogQuery } from '@/lib/types'

const LIMIT = 50

const ms = (value: number | null) => (value === null ? '–' : `${(value / 1000).toFixed(1)}s`)

const count = (value: number | null) => (value === null ? '–' : value.toLocaleString())

export function LogsPage() {
  const [params] = useSearchParams()
  const initial = params.get('q') ?? ''
  const [query, setQuery] = useState<GuideLogQuery>(initial ? { q: initial } : {})
  const [text, setText] = useState(initial)
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<GuideLogPage | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)

  const load = useCallback(() => {
    api.listGuideLogs(query, offset, LIMIT).then(setPage).catch(toastError)
  }, [query, offset])

  useEffect(() => {
    load()
  }, [load])

  const filter = (next: GuideLogQuery) => {
    setQuery(next)
    setOffset(0)
  }

  const search = (e: FormEvent) => {
    e.preventDefault()
    filter({ ...query, q: text.trim() || undefined })
  }

  const chips = (['visitorId', 'gaClientId', 'threadId'] as const).filter((key) => query[key])
  const total = page?.totalCount ?? 0

  return (
    <div className="p-6">
      <PageHeader
        title="대화 로그"
        description="방문자 안내 질문·답변. 방문자·GA·대화 ID를 누르면 그 값으로 거른다."
        actions={
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw /> 새로고침
          </Button>
        }
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <form onSubmit={search} className="flex gap-2">
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="질문 검색"
            className="w-64"
          />
          <Button type="submit" variant="outline" size="sm">
            검색
          </Button>
        </form>
        {chips.map((key) => (
          <Badge key={key} variant="secondary" className="gap-1">
            {key}: {query[key]}
            <button onClick={() => filter({ ...query, [key]: undefined })} aria-label="필터 해제">
              <X className="size-3" />
            </button>
          </Badge>
        ))}
        <span className="ml-auto text-sm text-muted-foreground tabular-nums">
          {total === 0 ? '0건' : `${offset + 1}–${Math.min(offset + LIMIT, total)} / ${total}건`}
        </span>
        <Button
          variant="outline"
          size="icon-sm"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - LIMIT))}
          aria-label="이전"
        >
          <ChevronLeft />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          disabled={offset + LIMIT >= total}
          onClick={() => setOffset(offset + LIMIT)}
          aria-label="다음"
        >
          <ChevronRight />
        </Button>
      </div>

      {page === null ? (
        <Skeleton className="mt-4 h-60" />
      ) : (
        <Table className="mt-4 table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">시각</TableHead>
              <TableHead>질문</TableHead>
              <TableHead className="w-24">모드</TableHead>
              <TableHead className="w-28 text-right">첫 토큰 / 전체</TableHead>
              <TableHead className="w-28 text-right">토큰 입력 / 출력</TableHead>
              <TableHead className="w-40">GA client_id</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                  기록이 없다.
                </TableCell>
              </TableRow>
            )}
            {page.items.map((log) => (
              <Fragment key={log.id}>
                <TableRow
                  className={cn('cursor-pointer', openId === log.id && 'bg-muted/50')}
                  onClick={() => setOpenId(openId === log.id ? null : log.id)}
                >
                  <TableCell className="text-xs text-muted-foreground">{formatDateTime(log.createdAt)}</TableCell>
                  <TableCell className="truncate">{log.question}</TableCell>
                  <TableCell>
                    <Badge variant={log.mode === 'llm' ? 'outline' : 'secondary'}>{log.mode}</Badge>
                    {!log.completed && (
                      <Badge variant="destructive" className="ml-1">
                        끊김
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">
                    {ms(log.firstTokenMs)} / {ms(log.totalMs)}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">
                    {count(log.inputTokens)} / {count(log.outputTokens)}
                  </TableCell>
                  <TableCell className="truncate font-mono text-xs">{log.gaClientId ?? '–'}</TableCell>
                </TableRow>
                {openId === log.id && (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={6} className="whitespace-normal">
                      <LogDetail log={log} onFilter={filter} query={query} />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

function LogDetail({
  log,
  query,
  onFilter,
}: {
  log: GuideLog
  query: GuideLogQuery
  onFilter: (query: GuideLogQuery) => void
}) {
  const ids = [
    ['visitorId', '방문자', log.visitorId],
    ['gaClientId', 'GA', log.gaClientId],
    ['threadId', '대화', log.threadId],
  ] as const

  return (
    <div className="grid gap-3 py-2 text-sm">
      <div>
        <div className="text-xs font-medium text-muted-foreground">질문</div>
        <p className="mt-1 whitespace-pre-wrap">{log.question}</p>
      </div>
      <div>
        <div className="text-xs font-medium text-muted-foreground">답변</div>
        <p className="mt-1 whitespace-pre-wrap">{log.answer || '–'}</p>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>검색 점수 {log.scores.length ? log.scores.map((s) => s.toFixed(3)).join(', ') : '–'}</span>
        <span>화면 표시 {log.anchors.length ? log.anchors.join(', ') : '–'}</span>
        <span>
          토큰 입력 {count(log.inputTokens)} (캐시 {count(log.cachedTokens)}) · 출력 {count(log.outputTokens)} (추론 {count(log.reasoningTokens)})
        </span>
        <span className="font-mono">Langfuse trace {log.traceId ?? '–'}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {ids.map(
          ([key, label, value]) =>
            value && (
              <Button
                key={key}
                variant="outline"
                size="xs"
                className="font-mono"
                onClick={() => onFilter({ ...query, [key]: value })}
              >
                {label}: {value}
              </Button>
            ),
        )}
      </div>
    </div>
  )
}
