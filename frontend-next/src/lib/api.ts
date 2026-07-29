export async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!resp.ok) {
    throw new Error(`API error: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

export async function getDashboard() {
  return fetchApi<unknown>("/api/dashboard/stats");
}

export async function getServers(tag?: string) {
  const params = tag ? `?tag=${encodeURIComponent(tag)}` : "";
  return fetchApi<unknown>(`/api/servers${params}`);
}

export async function getAlerts(params?: { severity?: string; status?: string }) {
  const search = new URLSearchParams();
  if (params?.severity) search.set("severity", params.severity);
  if (params?.status) search.set("status", params.status);
  return fetchApi<unknown>(`/api/alerts?${search.toString()}`);
}
