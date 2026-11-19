/** contracts/README.md 6장 quote 규칙 */
export function stripMarkdown(md: string): string {
  return md
    .replace(/!\[[^\]]*]\([^)]*\)/g, '')
    .replace(/\[([^\]]*)]\([^)]*\)/g, '$1')
    .replace(/^\s*(?:[-*+]|\d+\.|>)\s+/gm, '')
    .replace(/\*\*|__|`/g, '')
    .replace(/(^|[^\p{L}\p{N}])[*_]([^*_\n]+)[*_](?![\p{L}\p{N}])/gu, '$1$2')
}

export const collapseWhitespace = (s: string) => s.replace(/\s+/g, ' ').trim()

export const normalizeQuote = (s: string) => collapseWhitespace(stripMarkdown(s))
