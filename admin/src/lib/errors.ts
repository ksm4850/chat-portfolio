import { toast } from 'sonner'

export function toastError(error: unknown) {
  toast.error(error instanceof Error ? error.message : '알 수 없는 오류가 났다.')
}
