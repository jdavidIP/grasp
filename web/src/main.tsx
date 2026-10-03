import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/industry.css'
import './index.css'
import App from './App.tsx'
import { ToastProvider } from './components/Toast'
import { applyTheme, initialTheme } from './lib/theme'

// networkMode 'always' (default is 'online'): this app has no offline story, and the
// default pauses retries — leaving isLoading false and error null, indefinitely —
// whenever navigator.onLine looks false, which browsers do misreport at times (VPNs,
// captive portals). 'always' makes a query/mutation fail and populate `error` on its
// own merits instead of getting stuck invisible behind a connectivity guess.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { networkMode: 'always' },
    mutations: { networkMode: 'always' },
  },
})

// index.html's inline script already did this before first paint; this backs it up so the
// page never renders without a theme applied.
applyTheme(initialTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
)
