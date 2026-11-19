import { z } from 'zod'
import contract from '@contracts/tools.json'
import { normalizeQuote } from '@/lib/text'
import { useUi, viewKey, type View } from '@/store/ui'

type ToolName = 'navigate' | 'highlight'

type NavigateArgs = { view: View['name']; projectId?: string; tab?: string }
type HighlightArgs = { anchor: string; quote?: string }

const QUOTE_HIGHLIGHT = 'guide-quote'
const FOCUS_MS = 2600
export const MODAL_OPEN_MS = 320

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

function waitFor<T extends Element>(selector: string, timeoutMs = 3000): Promise<T> {
  return new Promise((resolve, reject) => {
    const started = performance.now()
    const tick = () => {
      const el = document.querySelector<T>(selector)
      if (el) return resolve(el)
      if (performance.now() - started > timeoutMs) return reject(new Error(`요소를 찾지 못함: ${selector}`))
      requestAnimationFrame(tick)
    }
    tick()
  })
}

const supportsHighlightApi = () => typeof CSS !== 'undefined' && 'highlights' in CSS

function clearQuote() {
  if (supportsHighlightApi()) CSS.highlights.delete(QUOTE_HIGHLIGHT)
}

/** 섹션의 렌더링된 텍스트에서 공백을 정규화해 quote 위치를 찾고, 문자 단위 Range 경계 목록을 돌려준다. */
function locateQuote(root: Element, quote: string): { node: Text; offset: number }[] | null {
  const target = normalizeQuote(quote)
  if (!target) return null
  const chars: { node: Text; offset: number }[] = []
  let text = ''
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
    const value = node.data
    for (let i = 0; i < value.length; i++) {
      const isSpace = /\s/.test(value[i])
      if (isSpace && (text === '' || text.endsWith(' '))) continue
      text += isSpace ? ' ' : value[i]
      chars.push({ node, offset: i })
    }
  }
  const start = text.indexOf(target)
  if (start < 0) return null
  return chars.slice(start, start + target.length)
}

async function paintQuote(chars: { node: Text; offset: number }[]) {
  const first = chars[0]
  const duration = Math.min(650, chars.length * 14)
  const started = performance.now()
  while (true) {
    const progress = Math.min(1, (performance.now() - started) / duration)
    const last = chars[Math.max(0, Math.ceil(progress * chars.length) - 1)]
    const range = document.createRange()
    range.setStart(first.node, first.offset)
    range.setEnd(last.node, last.offset + 1)
    CSS.highlights.set(QUOTE_HIGHLIGHT, new Highlight(range))
    if (progress >= 1) return
    await new Promise(requestAnimationFrame)
  }
}

function focusSection(section: HTMLElement) {
  const root = section.closest<HTMLElement>('[data-view-key]')
  if (!root) return
  root.querySelectorAll('[data-focused]').forEach((el) => el.removeAttribute('data-focused'))
  section.setAttribute('data-focused', '')
  root.setAttribute('data-focusing', '')
  const token = String(performance.now())
  root.dataset.focusToken = token
  setTimeout(() => {
    if (root.dataset.focusToken !== token) return
    root.removeAttribute('data-focusing')
    section.removeAttribute('data-focused')
  }, FOCUS_MS)
}

function pulseSection(section: HTMLElement) {
  section.classList.remove('anchor-highlight')
  void section.offsetWidth
  section.classList.add('anchor-highlight')
}

const implementations: Record<ToolName, (args: never) => Promise<void>> = {
  navigate: async ({ view, projectId, tab }: NavigateArgs) => {
    if (view === 'project' && !projectId) throw new Error('view=project에는 projectId가 필요함')
    const next: View = view === 'project' ? { name: 'project', projectId: projectId!, tab } : { name: view }
    const ui = useUi.getState()
    if (ui.screen === 'landing') ui.openApp({ chat: ui.chatOpen })
    const current: View = ui.project ? { name: 'project', ...ui.project } : ui.page
    if (viewKey(current) !== viewKey(next)) clearQuote()
    const opening = next.name === 'project' && !ui.project
    if (next.name === 'project') ui.openProject({ projectId: next.projectId, tab: next.tab })
    else ui.setPage(next)
    const root = await waitFor<HTMLElement>(`[data-view-key="${CSS.escape(viewKey(next))}"][data-ready="true"]`)
    if (opening) await sleep(MODAL_OPEN_MS)
    root.closest('[data-stage]')?.scrollTo({ top: 0, behavior: 'smooth' })
  },
  highlight: async ({ anchor, quote }: HighlightArgs) => {
    const section = await waitFor<HTMLElement>(`[data-anchor="${CSS.escape(anchor)}"]`)
    clearQuote()
    const chars = quote && supportsHighlightApi() ? locateQuote(section, quote) : null
    const scrollTarget = chars?.[0].node.parentElement ?? section
    scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'center' })
    focusSection(section)
    await sleep(320)
    if (chars) await paintQuote(chars)
    else pulseSection(section)
  },
}

const registry = new Map(
  contract.tools
    .filter((t): t is typeof t & { name: ToolName } => t.name in implementations)
    .map((t) => [t.name, { version: t.version, schema: z.fromJSONSchema(t.parameters as never), run: implementations[t.name] }]),
)

export const capabilities = [...registry.entries()].map(([name, t]) => `${name}@${t.version}`)

export async function runTool(name: string, args: unknown): Promise<void> {
  const tool = registry.get(name as ToolName)
  if (!tool) throw new Error(`지원하지 않는 툴: ${name}`)
  const parsed = tool.schema.safeParse(args)
  if (!parsed.success) throw new Error(`인자 검증 실패: ${parsed.error.message}`)
  await tool.run(parsed.data as never)
}

export const navigate = (args: NavigateArgs) => runTool('navigate', args)
