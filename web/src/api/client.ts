export const API_URL = import.meta.env.VITE_API_URL

// FastAPI's shape for a 422 Pydantic validation error: `detail` is an array of these,
// not a string — rendering it directly gives "[object Object]".
interface ValidationErrorDetail {
  loc: (string | number)[]
  msg: string
}

function isValidationErrors(detail: unknown): detail is ValidationErrorDetail[] {
  return (
    Array.isArray(detail) &&
    detail.every(
      (item) => typeof item === 'object' && item !== null && typeof item.msg === 'string',
    )
  )
}

function errorMessage(body: unknown, fallback: string): string {
  const detail = typeof body === 'object' && body !== null ? (body as { detail?: unknown }).detail : undefined
  if (typeof detail === 'string') return detail
  if (isValidationErrors(detail)) {
    return detail
      .map((item) => {
        const field = item.loc.filter((part) => part !== 'body').join('.')
        return field ? `${field}: ${item.msg}` : item.msg
      })
      .join('; ')
  }
  return fallback
}

export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(errorMessage(body, response.statusText))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json()
}

export const DEFAULT_TIMEOUT_MS = 30_000
// Chat answers and deck/quiz generation make several LLM calls, each allowed 120s with
// retries server-side (app/generation/llm.py), so they get a far longer budget.
export const GENERATION_TIMEOUT_MS = 300_000

const TIMEOUT_MESSAGE = 'The server took too long to answer. Try again.'

// Matched by name, not `instanceof DOMException`: the abort reason can come from another
// realm's DOMException (jsdom's, in tests).
function isTimeout(cause: unknown): boolean {
  return typeof cause === 'object' && cause !== null && (cause as { name?: unknown }).name === 'TimeoutError'
}

// The single place every api/*.ts call goes through: resolves the URL, aborts a request
// the server never answers, and turns a network-level failure (API unreachable, DNS,
// CORS — fetch() itself rejects, never producing a Response) into a message as readable
// as an HTTP error's, instead of the browser's bare "Failed to fetch".
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, signal: AbortSignal.timeout(timeoutMs) })
  } catch (cause) {
    if (isTimeout(cause)) throw new Error(TIMEOUT_MESSAGE, { cause })
    throw new Error('Could not reach the API server. Check that it is running.', { cause })
  }
  // The signal also covers reading the body, which can stall after the headers arrive.
  try {
    return await handleResponse<T>(response)
  } catch (cause) {
    if (isTimeout(cause)) throw new Error(TIMEOUT_MESSAGE, { cause })
    throw cause
  }
}
