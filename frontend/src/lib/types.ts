export type Profile = { name: string }

export type Career = {
  company: string
  period: string
  description: string
  roles: string[]
  projectIds: string[]
}

export type TabSummary = { id: string; label: string }

export type ProjectSummary = {
  id: string
  company: string
  title: string
  period: string
  summary: string
  stacks: string[]
  url: string | null
  media: string[]
  tabs: TabSummary[]
}

export type SkillGroup = { category: string; items: string[] }

export type Portfolio = {
  profile: Profile
  careers: Career[]
  projects: ProjectSummary[]
  skills: SkillGroup[]
}

export type Section = { anchor: string; level: number; title: string; body: string }

export type ProjectDetail = Omit<ProjectSummary, 'tabs'> & {
  tabs: (TabSummary & { sections: Section[] })[]
}

export type SourceLocation = { projectId: string; tab: string; anchor: string }

export type Source = {
  title: string
  snippet: string
  score: number
  location: SourceLocation | null
}
