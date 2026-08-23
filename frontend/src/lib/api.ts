export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new ApiError(text || `Request failed: ${res.status}`, res.status)
  }
  return (await res.json()) as T
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return parse<T>(await fetch(`${API_BASE}${path}`, { signal, cache: "no-store" }))
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return parse<T>(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  )
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  return parse<T>(await fetch(`${API_BASE}${path}`, { method: "POST", body: form }))
}
