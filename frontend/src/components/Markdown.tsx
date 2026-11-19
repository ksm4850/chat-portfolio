import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { toPublicUrl } from '@/lib/media'

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose prose-sm prose-neutral max-w-none prose-headings:font-semibold prose-img:rounded-lg prose-img:border prose-li:my-0.5">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          img: ({ src, alt }) => <img src={toPublicUrl(src as string)} alt={alt ?? ''} loading="lazy" />,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
