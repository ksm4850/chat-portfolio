import { useEffect, useState } from 'react'
import { NavLink, useParams } from 'react-router'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { RefreshCw, Save } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { PageHeader } from '@/components/PageHeader'
import { api } from '@/lib/api'
import { toastError } from '@/lib/errors'
import { toMediaUrl } from '@/lib/media'
import { cn } from '@/lib/utils'
import type { IngestResult, SourceFile, SourceFileContent } from '@/lib/types'

const ingested = (r: IngestResult) =>
  `재수집 완료: 프로젝트 ${r.projects}, 문서 ${r.documents}, 섹션 ${r.sections}, 청크 ${r.chunks}`

export function PortfolioPage() {
  const { file } = useParams()
  const [files, setFiles] = useState<SourceFile[] | null>(null)
  const [reingesting, setReingesting] = useState(false)

  useEffect(() => {
    api.listSourceFiles().then(setFiles).catch(toastError)
  }, [])

  async function reingest() {
    setReingesting(true)
    try {
      toast.success(ingested(await api.reingest()))
    } catch (e) {
      toastError(e)
    } finally {
      setReingesting(false)
    }
  }

  const projects = new Map<string, SourceFile[]>()
  for (const f of files ?? []) projects.set(f.projectTitle, [...(projects.get(f.projectTitle) ?? []), f])

  return (
    <div className="flex h-full flex-col p-6">
      <PageHeader
        title="포트폴리오 원본"
        description="content/portfolio 의 탭별 md. 저장하면 파일에 쓰고 방문자 화면 섹션과 'me' 캐릭터 지식을 다시 수집한다."
        actions={
          <Button variant="outline" size="sm" onClick={reingest} disabled={reingesting}>
            <RefreshCw className={cn(reingesting && 'animate-spin')} /> 전체 재수집
          </Button>
        }
      />
      <div className="mt-4 grid min-h-0 flex-1 grid-cols-[14rem_1fr] gap-4">
        <nav className="overflow-y-auto rounded-lg border p-2 text-sm">
          {files === null && <Skeleton className="h-40" />}
          {[...projects].map(([project, tabs]) => (
            <div key={project} className="mb-2">
              <div className="px-2 py-1 text-xs font-medium text-muted-foreground">{project}</div>
              {tabs.map((f) => (
                <NavLink
                  key={f.file}
                  to={`/portfolio/${f.file}`}
                  className={({ isActive }) =>
                    cn('block rounded-md px-2 py-1 hover:bg-muted', isActive && 'bg-muted font-medium')
                  }
                >
                  {f.tabLabel}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        {file ? (
          <SourceEditor key={file} file={file} />
        ) : (
          <p className="text-sm text-muted-foreground">왼쪽에서 탭을 고른다.</p>
        )}
      </div>
    </div>
  )
}

function SourceEditor({ file }: { file: string }) {
  const [source, setSource] = useState<SourceFileContent | null>(null)
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const dirty = source !== null && content !== source.content

  useEffect(() => {
    api
      .getSourceFile(file)
      .then((s) => {
        setSource(s)
        setContent(s.content)
      })
      .catch(toastError)
  }, [file])

  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  async function save() {
    setSaving(true)
    try {
      const result = await api.saveSourceFile(file, content)
      setSource((s) => s && { ...s, content })
      toast.success(ingested(result))
    } catch (e) {
      toastError(e)
    } finally {
      setSaving(false)
    }
  }

  if (!source) return <Skeleton className="h-full" />

  return (
    <Tabs defaultValue="edit" className="flex min-h-0 flex-col">
      <div className="flex items-center gap-2">
        <TabsList>
          <TabsTrigger value="edit">편집</TabsTrigger>
          <TabsTrigger value="preview">미리보기</TabsTrigger>
        </TabsList>
        <Badge variant="outline">{source.file}</Badge>
        <span className="truncate text-sm text-muted-foreground">
          {source.projectTitle} › {source.tabLabel}
        </span>
        {dirty && <Badge variant="secondary">변경됨</Badge>}
        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm" disabled={!dirty || saving} onClick={() => setContent(source.content)}>
            되돌리기
          </Button>
          <Button size="sm" disabled={!dirty || saving} onClick={save}>
            <Save /> {saving ? '재수집 중…' : '저장 후 재수집'}
          </Button>
        </div>
      </div>
      <TabsContent value="edit" className="mt-2 min-h-0 flex-1">
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="h-full resize-none font-mono text-xs"
          spellCheck={false}
        />
      </TabsContent>
      <TabsContent value="preview" className="mt-2 min-h-0 flex-1 overflow-y-auto rounded-lg border p-4">
        <article className="prose prose-sm max-w-none">
          <Markdown
            remarkPlugins={[remarkGfm]}
            components={{ img: ({ src, alt }) => <img src={toMediaUrl(src as string)} alt={alt ?? ''} loading="lazy" /> }}
          >
            {content}
          </Markdown>
        </article>
      </TabsContent>
    </Tabs>
  )
}
