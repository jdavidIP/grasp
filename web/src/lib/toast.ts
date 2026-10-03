import { createContext, useContext } from 'react'

export const TOAST_MS = 1900

// Outside a ToastProvider this is a no-op, so components using it stay testable alone.
export const ToastContext = createContext<(message: string) => void>(() => {})

export function useToast(): (message: string) => void {
  return useContext(ToastContext)
}
