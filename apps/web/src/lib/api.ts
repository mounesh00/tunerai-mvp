const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
};

export type Project = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
  domain: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  health: () => request<{ status: string; service: string; version: string }>("/api/v1/health"),

  register: (data: {
    email: string;
    password: string;
    full_name?: string;
    organization_name?: string;
  }) => request<User>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  me: (token: string) => request<User>("/api/v1/auth/me", {}, token),

  listProjects: (token: string) => request<Project[]>("/api/v1/projects", {}, token),

  createProject: (
    token: string,
    data: { name: string; description?: string; domain?: string }
  ) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }, token),

  getProject: (token: string, id: string) =>
    request<Project>(`/api/v1/projects/${id}`, {}, token),

  createDataset: (
    token: string,
    data: { name: string; description?: string; project_id: string }
  ) =>
    request<Dataset>("/api/v1/datasets", {
      method: "POST",
      body: JSON.stringify(data),
    }, token),

  listDatasets: (token: string, projectId: string) =>
    request<DatasetWithVersions[]>(`/api/v1/datasets/project/${projectId}`, {}, token),

  getDataset: (token: string, id: string) =>
    request<DatasetWithVersions>(`/api/v1/datasets/${id}`, {}, token),

  uploadDataset: async (token: string, datasetId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(
      `${API_URL}/api/v1/datasets/${datasetId}/upload`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Upload failed: ${res.status}`);
    }
    return res.json() as Promise<DatasetVersion>;
  },

  getQualityReport: (token: string, datasetId: string, versionId: string) =>
    request<{ dataset_id: string; version_id: string; status: string; report: Record<string, unknown> }>(
      `/api/v1/datasets/${datasetId}/versions/${versionId}/report`,
      {},
      token
    ),
};

export type Dataset = {
  id: string;
  organization_id: string;
  project_id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type DatasetVersion = {
  id: string;
  dataset_id: string;
  version: string;
  storage_path: string;
  original_filename: string;
  format: string;
  total_records: number | null;
  valid_records: number | null;
  invalid_records: number | null;
  duplicate_count: number | null;
  duplicate_percentage: number | null;
  avg_tokens: number | null;
  max_tokens: number | null;
  estimated_training_tokens: number | null;
  train_size: number | null;
  validation_size: number | null;
  quality_score: number | null;
  quality_report: Record<string, unknown> | null;
  warnings: unknown[] | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type DatasetWithVersions = Dataset & { versions: DatasetVersion[] };
