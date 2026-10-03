import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { TOAST_MS, ToastContext } from '../lib/toast'
import './Toast.css'

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)

  const show = useCallback((next: string) => {
    window.clearTimeout(timer.current)
    setMessage(next)
    timer.current = window.setTimeout(() => setMessage(null), TOAST_MS)
  }, [])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  return (
    <ToastContext value={show}>
      {children}
      <div role="status" aria-live="polite" className="toast-region">
        {message && (
          <div className="toast blueprint elev-md">
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            {message}
          </div>
        )}
      </div>
    </ToastContext>
  )
}
