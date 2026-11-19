import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ChunkList } from '@/components/character/ChunkList'
import { DocumentForm } from '@/components/character/DocumentForm'
import { api } from '@/lib/api'
import { toastError } from '@/lib/errors'
import { formatDateTime, isPortfolioSource, portfolioFile } from '@/lib/format'
import type { DocumentDetail, DocumentInput } from '@/lib/types'

export function DocumentDialog({
  characterId,
  documentId,
  onClose,
  onSaved,
}: {
  characterId: string
  documentId: string | null
  onClose: () => void
  onSaved: () => void
}) {
  return (
    <Dialog open={documentId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[90vh] flex-col sm:max-w-3xl">
        {documentId && (
          <DocumentBody key={documentId} characterId={characterId} documentId={documentId} onSaved={onSaved} />
        )}
      </DialogContent>
    </Dialog>
  )
}

function DocumentBody({
  characterId,
  documentId,
  onSaved,
}: {
  characterId: string
  documentId: string
  onSaved: () => void
}) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    api.getDocument(characterId, documentId).then(setDetail).catch(toastError)
  }, [characterId, documentId])

  async function save(input: DocumentInput) {
    if (!detail) return
    const changed: Partial<DocumentInput> = {}
    if (input.title !== detail.title) changed.title = input.title
    if (input.source !== detail.source) changed.source = input.source
    if (input.content !== detail.content) changed.content = input.content
    try {
      await api.updateDocument(characterId, detail.id, changed)
      setDetail(await api.getDocument(characterId, detail.id))
      setEditing(false)
      onSaved()
      toast.success(changed.content ? '저장하고 청크를 다시 만들었다.' : '저장했다.')
    } catch (e) {
      toastError(e)
    }
  }

  const imported = detail ? isPortfolioSource(detail.source) : false

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 pr-6">
          {detail?.title ?? '문서'}
          {detail && <Badge variant="outline">{detail.source}</Badge>}
        </DialogTitle>
        {detail && (
          <DialogDescription>
            청크 {detail.chunkCount}개 · 수정 {formatDateTime(detail.updatedAt)}
          </DialogDescription>
        )}
      </DialogHeader>
      {!detail ? (
        <Skeleton className="h-60" />
      ) : editing ? (
        <div className="overflow-y-auto">
          <DocumentForm
            initial={{ title: detail.title, source: detail.source, content: detail.content }}
            submitLabel="저장"
            onSubmit={save}
            onCancel={() => setEditing(false)}
          />
        </div>
      ) : (
        <Tabs defaultValue="chunks" className="min-h-0 flex-1">
          <div className="flex items-center">
            <TabsList>
              <TabsTrigger value="chunks">청크 {detail.chunks.length}</TabsTrigger>
              <TabsTrigger value="content">원문</TabsTrigger>
            </TabsList>
            {imported ? (
              <Button variant="outline" size="sm" className="ml-auto" asChild>
                <Link to={`/portfolio/${portfolioFile(detail.source)}`}>원본 md 편집</Link>
              </Button>
            ) : (
              <Button size="sm" className="ml-auto" onClick={() => setEditing(true)}>
                수정
              </Button>
            )}
          </div>
          <TabsContent value="chunks" className="mt-2 overflow-y-auto">
            <ChunkList chunks={detail.chunks} />
          </TabsContent>
          <TabsContent value="content" className="mt-2 overflow-y-auto">
            <pre className="rounded-lg bg-muted p-3 font-mono text-xs whitespace-pre-wrap">{detail.content}</pre>
          </TabsContent>
        </Tabs>
      )}
    </>
  )
}
