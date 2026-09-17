export const API_URL = import.meta.env.VITE_API_URL

export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? response.statusText)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json()
}
