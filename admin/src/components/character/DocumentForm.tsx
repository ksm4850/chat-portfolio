import { useState, type ChangeEvent } from 'react'
import { Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { DocumentInput } from '@/lib/types'

export function DocumentForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: DocumentInput
  submitLabel: string
  onSubmit: (input: DocumentInput) => Promise<void>
  onCancel?: () => void
}) {
  const [form, setForm] = useState<DocumentInput>(initial ?? { title: '', source: 'profile', content: '' })
  const [pending, setPending] = useState(false)

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const content = await file.text()
    setForm((f) => ({ ...f, content, title: f.title || file.name.replace(/\.(md|txt)$/i, '') }))
  }

  return (
    <form
      className="grid gap-4"
      onSubmit={async (e) => {
        e.preventDefault()
        setPending(true)
        try {
          await onSubmit(form)
        } finally {
          setPending(false)
        }
      }}
    >
      <div className="grid grid-cols-[2fr_1fr] gap-3">
        <div className="grid gap-1.5">
          <Label htmlFor="doc-title">제목</Label>
          <Input
            id="doc-title"
            value={form.title}
            maxLength={200}
            required
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="doc-source">
            출처 <span className="font-normal text-muted-foreground">profile, kakao, note…</span>
          </Label>
          <Input
            id="doc-source"
            value={form.source}
            maxLength={50}
            required
            onChange={(e) => setForm({ ...form, source: e.target.value })}
          />
        </div>
      </div>
      <div className="grid gap-1.5">
        <div className="flex items-center">
          <Label htmlFor="doc-content">
            내용 <span className="font-normal text-muted-foreground">빈 줄로 나눈 문단 단위로 청크가 된다</span>
          </Label>
          <Button type="button" variant="outline" size="sm" className="ml-auto" asChild>
            <label>
              <Upload /> 파일 불러오기
              <input type="file" accept=".md,.txt,text/markdown,text/plain" hidden onChange={readFile} />
            </label>
          </Button>
        </div>
        <Textarea
          id="doc-content"
          value={form.content}
          rows={14}
          required
          className="max-h-[50vh] font-mono text-xs"
          onChange={(e) => setForm({ ...form, content: e.target.value })}
        />
      </div>
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            취소
          </Button>
        )}
        <Button type="submit" disabled={pending}>
          {pending ? '임베딩 중…' : submitLabel}
        </Button>
      </div>
    </form>
  )
}
