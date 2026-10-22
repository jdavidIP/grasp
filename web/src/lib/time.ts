export function formatTime(seconds: number): string {
  const total = Math.floor(seconds)
  const hours = Math.floor(total / 3600)
  const mins = Math.floor((total % 3600) / 60)
  const secs = (total % 60).toString().padStart(2, '0')
  return hours > 0 ? `${hours}:${mins.toString().padStart(2, '0')}:${secs}` : `${mins}:${secs}`
}

// A chunk's span: "4:58–6:21", or just the start for rows stored before the end was (#50).
export function formatSpan(start: number, end: number | null): string {
  return end === null ? formatTime(start) : `${formatTime(start)}–${formatTime(end)}`
}

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 86400],
  ['month', 30 * 86400],
  ['week', 7 * 86400],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
  ['second', 1],
]

const relativeFormat = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = (new Date(iso).getTime() - now.getTime()) / 1000
  const [unit, size] = RELATIVE_UNITS.find(([, s]) => Math.abs(seconds) >= s) ?? (['second', 1] as const)
  return relativeFormat.format(Math.round(seconds / size), unit)
}
