import { ArrowUp } from 'lucide-react'
import { memo, useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

type Props = {
  onSubmit: (text: string) => void
  disabled?: boolean
  size?: 'lg' | 'default'
  placeholder?: string
  autoFocus?: boolean
}

export const Composer = memo(function Composer({ onSubmit, disabled, size = 'default', placeholder, autoFocus }: Props) {
  const [text, setText] = useState('')

  const submit = () => {
    if (!text.trim() || disabled) return
    onSubmit(text)
    setText('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const large = size === 'lg'
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className={cn(
        'rounded-xl border bg-card shadow-xs transition focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/20',
        large ? 'p-2' : 'flex items-end gap-2 p-1.5',
      )}
    >
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={large ? 2 : 1}
        autoFocus={autoFocus}
        placeholder={placeholder ?? '무엇이든 편하게 물어봐 주세요'}
        className={cn(
          'resize-none border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent',
          large ? 'min-h-16 text-base md:text-[15px]' : 'max-h-32 min-h-9 text-sm',
        )}
      />
      <div className={cn(large && 'flex items-center justify-between px-2 pb-0.5')}>
        {large && <span className="text-xs text-muted-foreground">Enter로 전송 · Shift+Enter 줄바꿈</span>}
        <Button type="submit" size={large ? 'icon-lg' : 'icon'} disabled={disabled || !text.trim()} aria-label="전송">
          <ArrowUp />
        </Button>
      </div>
    </form>
  )
})
