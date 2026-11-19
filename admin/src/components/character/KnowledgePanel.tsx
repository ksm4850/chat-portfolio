import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ConfirmButton } from '@/components/ConfirmButton'
import { DocumentDialog } from '@/components/character/DocumentDialog'
import { DocumentForm } from '@/components/character/DocumentForm'
import { api } from '@/lib/api'
import { toastError } from '@/lib/errors'
import { formatDateTime, isPortfolioSource, portfolioFile } from '@/lib/format'
import type { DocumentInput, KnowledgeDocument } from '@/lib/types'

export function KnowledgePanel({ characterId }: { characterId: string }) {
  const [documents, setDocuments] = useState<KnowledgeDocument[] | null>(null)
  const [adding, setAdding] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)

  const reload = useCallback(
    () => api.listDocuments(characterId).then(setDocuments).catch(toastError),
    [characterId],
  )

  useEffect(() => {
    reload()
  }, [reload])

  async function add(input: DocumentInput) {
    try {
      const created = await api.addDocument(characterId, input)
      toast.success(`적재했다. 청크 ${created.chunkCount}개`)
      setAdding(false)
      reload()
    } catch (e) {
      toastError(e)
    }
  }

  async function remove(document: KnowledgeDocument) {
    try {
      await api.deleteDocument(characterId, document.id)
      reload()
    } catch (e) {
      toastError(e)
    }
  }

  const own = documents?.filter((d) => !isPortfolioSource(d.source)) ?? []
  const imported = documents?.filter((d) => isPortfolioSource(d.source)) ?? []

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader>
          <CardTitle>관리자 문서</CardTitle>
          <CardDescription>자기소개 Q&A, 메모처럼 직접 넣은 기억. 수정하면 청크를 다시 만든다.</CardDescription>
          <CardAction>
            <Button size="sm" onClick={() => setAdding(true)}>
              <Plus /> 문서 추가
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <DocumentTable
            documents={own}
            loading={documents === null}
            empty="직접 넣은 문서가 없다."
            onOpen={setOpenId}
            actions={(document) => (
              <ConfirmButton
                variant="ghost"
                size="xs"
                title={`'${document.title}' 문서를 삭제할까?`}
                description="청크와 임베딩도 함께 지워진다."
                onConfirm={() => remove(document)}
              >
                삭제
              </ConfirmButton>
            )}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>포트폴리오 문서</CardTitle>
          <CardDescription>
            content/portfolio 원본 md 를 수집한 문서. 여기서는 읽기만 하고, 고칠 때는 원본 md 를 편집한다.
          </CardDescription>
          <CardAction>
            <Button size="sm" variant="outline" asChild>
              <Link to="/portfolio">원본 관리</Link>
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <DocumentTable
            documents={imported}
            loading={documents === null}
            empty="수집된 포트폴리오 문서가 없다."
            onOpen={setOpenId}
            actions={(document) => (
              <Button variant="ghost" size="xs" asChild>
                <Link to={`/portfolio/${portfolioFile(document.source)}`}>원본 편집</Link>
              </Button>
            )}
          />
        </CardContent>
      </Card>

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>문서 추가</DialogTitle>
          </DialogHeader>
          <DocumentForm submitLabel="적재" onSubmit={add} onCancel={() => setAdding(false)} />
        </DialogContent>
      </Dialog>

      <DocumentDialog
        characterId={characterId}
        documentId={openId}
        onClose={() => setOpenId(null)}
        onSaved={reload}
      />
    </div>
  )
}

function DocumentTable({
  documents,
  loading,
  empty,
  onOpen,
  actions,
}: {
  documents: KnowledgeDocument[]
  loading: boolean
  empty: string
  onOpen: (id: string) => void
  actions: (document: KnowledgeDocument) => React.ReactNode
}) {
  if (loading) return <p className="text-sm text-muted-foreground">불러오는 중…</p>
  if (documents.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>제목</TableHead>
          <TableHead>출처</TableHead>
          <TableHead className="text-right">청크</TableHead>
          <TableHead>수정</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((document) => (
          <TableRow key={document.id}>
            <TableCell className="max-w-72">
              <button className="truncate text-left hover:underline" onClick={() => onOpen(document.id)}>
                {document.title}
              </button>
            </TableCell>
            <TableCell>
              <Badge variant="outline">{document.source}</Badge>
            </TableCell>
            <TableCell className="text-right tabular-nums">{document.chunkCount}</TableCell>
            <TableCell className="text-muted-foreground">{formatDateTime(document.updatedAt)}</TableCell>
            <TableCell className="text-right">{actions(document)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
