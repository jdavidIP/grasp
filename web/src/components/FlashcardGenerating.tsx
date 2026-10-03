import { useEffect, useState } from 'react'

// Generation is one request with no progress reported, so this says what is happening
// and how long it has taken rather than ticking invented steps.
export function FlashcardGenerating() {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <section className="fc-generating">
      <div aria-live="polite">
        <h4>Generating deck…</h4>
        <p className="text-muted">
          Retrieving passages, drafting cards and checking each one against the transcript.
        </p>
      </div>
      <p className="text-muted tabular fc-elapsed">{seconds}s elapsed</p>
    </section>
  )
}
