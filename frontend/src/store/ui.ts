import { create } from 'zustand'

export type PageView = { name: 'home' } | { name: 'career' } | { name: 'skills' }
export type ProjectRef = { projectId: string; tab?: string }
export type View = PageView | ({ name: 'project' } & ProjectRef)

type UiState = {
  screen: 'landing' | 'app'
  chatOpen: boolean
  logOpen: boolean
  page: PageView
  project: ProjectRef | null
  setPage: (page: PageView) => void
  openProject: (project: ProjectRef) => void
  closeProject: () => void
  openApp: (opts: { chat: boolean }) => void
  showLanding: () => void
  setChatOpen: (open: boolean) => void
  toggleLog: () => void
}

export const useUi = create<UiState>((set) => ({
  screen: 'landing',
  chatOpen: true,
  logOpen: false,
  page: { name: 'home' },
  project: null,
  setPage: (page) => set({ page, project: null }),
  openProject: (project) => set({ project }),
  closeProject: () => set({ project: null }),
  openApp: ({ chat }) => set({ screen: 'app', chatOpen: chat }),
  showLanding: () => set({ screen: 'landing' }),
  setChatOpen: (chatOpen) => set({ chatOpen }),
  toggleLog: () => set((s) => ({ logOpen: !s.logOpen })),
}))

export const viewKey = (v: View) =>
  v.name === 'project' ? `project:${v.projectId}:${v.tab ?? ''}` : v.name
