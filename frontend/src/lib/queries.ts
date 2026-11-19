import { useCallback, useEffect, useState } from 'react'
import { fetchPortfolio, fetchProject } from '@/lib/api'
import type { Portfolio, ProjectDetail } from '@/lib/types'

type Result<T> = { data: T | null; error: Error | null }

const cache = new Map<string, Promise<unknown>>()

function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  if (!cache.has(key)) {
    const p = load().catch((e) => {
      cache.delete(key)
      throw e
    })
    cache.set(key, p)
  }
  return cache.get(key) as Promise<T>
}

function useCached<T>(key: string | null, load: () => Promise<T>): Result<T> {
  const [state, setState] = useState<Result<T> & { key: string | null }>({ key: null, data: null, error: null })
  useEffect(() => {
    if (!key) return
    let alive = true
    cached(key, load).then(
      (data) => alive && setState({ key, data, error: null }),
      (error: Error) => alive && setState({ key, data: null, error }),
    )
    return () => {
      alive = false
    }
  }, [key, load])
  return state.key === key ? state : { data: null, error: null }
}

export const usePortfolio = () => useCached<Portfolio>('portfolio', fetchPortfolio)

export function useProject(projectId: string) {
  const load = useCallback(() => fetchProject(projectId), [projectId])
  return useCached<ProjectDetail>(`project:${projectId}`, load)
}
