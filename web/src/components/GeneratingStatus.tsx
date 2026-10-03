import { useEffect, useState } from 'react'
import './Forms.css'

// Generation is one request with no progress reported, so this says what is happening
// and how long it has taken rather than ticking invented steps.
export function GeneratingStatus({ heading, noun }: { heading: string; noun: string }) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <section className="form-generating">
      <div aria-live="polite">
        <h4>{heading}</h4>
        <p className="text-muted">
          Retrieving passages, drafting {noun} and checking each one against the transcript.
        </p>
      </div>
      <p className="text-muted tabular form-elapsed">{seconds}s elapsed</p>
    </section>
  )
}
