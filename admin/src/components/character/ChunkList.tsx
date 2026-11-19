import { Badge } from '@/components/ui/badge'
import type { Chunk } from '@/lib/types'

export function MetaBadges({ meta }: { meta: Record<string, unknown> | null }) {
  if (!meta) return null
  const path = typeof meta.path === 'string' ? meta.path : null
  const anchor = typeof meta.anchor === 'string' ? meta.anchor : null
  return (
    <span className="flex min-w-0 flex-wrap items-center gap-1">
      {anchor && <Badge variant="outline">#{anchor}</Badge>}
      {path && <span className="truncate text-xs text-muted-foreground">{path}</span>}
    </span>
  )
}

export function ChunkList({ chunks }: { chunks: Chunk[] }) {
  return (
    <ol className="grid gap-2">
      {chunks.map((chunk) => (
        <li key={chunk.position} className="rounded-lg border p-3">
          <div className="mb-1.5 flex items-center gap-2">
            <Badge variant="secondary">{chunk.position + 1}</Badge>
            <MetaBadges meta={chunk.meta} />
            <span className="ml-auto text-xs text-muted-foreground">{chunk.content.length}자</span>
          </div>
          <p className="text-sm whitespace-pre-wrap">{chunk.content}</p>
        </li>
      ))}
    </ol>
  )
}
