import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
