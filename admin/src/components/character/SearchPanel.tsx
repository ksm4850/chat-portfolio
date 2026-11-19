import { useState } from 'react'
import { Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { MetaBadges } from '@/components/character/ChunkList'
import { api } from '@/lib/api'
import { toastError } from '@/lib/errors'
import type { SearchHit } from '@/lib/types'

export function HitList({ hits }: { hits: SearchHit[] }) {
  return (
    <ol className="grid gap-2">
      {hits.map((hit, index) => (
        <li key={index} className="rounded-lg border p-3">
          <div className="mb-1.5 flex items-center gap-2">
            <Badge variant={hit.score >= 0.55 ? 'default' : 'secondary'} className="tabular-nums">
              {hit.score.toFixed(3)}
            </Badge>
            <span className="truncate text-sm font-medium">{hit.title}</span>
            <MetaBadges meta={hit.meta} />
          </div>
          <p className="text-sm whitespace-pre-wrap text-muted-foreground">{hit.content}</p>
        </li>
      ))}
    </ol>
  )
}

export function SearchPanel({ characterId }: { characterId: string }) {
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState('6')
  const [hits, setHits] = useState<SearchHit[] | null>(null)
  const [pending, setPending] = useState(false)

  async function search() {
    setPending(true)
    try {
      setHits(await api.search(characterId, query, Number(limit)))
    } catch (e) {
      toastError(e)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="grid gap-4">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          search()
        }}
      >
        <Input placeholder="방문자가 할 법한 질문" value={query} required onChange={(e) => setQuery(e.target.value)} />
        <Select value={limit} onValueChange={setLimit}>
          <SelectTrigger className="w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {['4', '6', '10', '20'].map((n) => (
              <SelectItem key={n} value={n}>
                {n}개
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="submit" disabled={pending}>
          <Search /> 검색
        </Button>
      </form>
      <p className="text-xs text-muted-foreground">점수는 코사인 유사도. 0.55 이상은 진하게 표시한다(안내 화면 이동 기준).</p>
      {hits && (hits.length ? <HitList hits={hits} /> : <p className="text-sm text-muted-foreground">결과가 없다.</p>)}
    </div>
  )
}
