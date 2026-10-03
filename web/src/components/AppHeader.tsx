import { Link } from 'react-router'
import { useTheme } from '../lib/theme'
import './AppHeader.css'

// Lucide sun/moon paths at stroke 1.5, inlined as in the design handoff. Add
// lucide-react once more icons are needed.
function SunIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  )
}

export function AppHeader({ meta }: { meta: string }) {
  const [theme, toggleTheme] = useTheme()
  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'

  return (
    <header className="app-header">
      <div className="nav app-header-inner">
        <Link to="/" className="nav-brand app-header-brand">
          GRASP
        </Link>
        <span className="text-muted app-header-meta">{meta}</span>
        <button type="button" className="btn btn-icon" onClick={toggleTheme} title={label} aria-label={label}>
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </header>
  )
}
