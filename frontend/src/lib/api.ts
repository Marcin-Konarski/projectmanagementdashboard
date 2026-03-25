const API_BASE = "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed: ${res.status}`);
  }

  if (res.status === 204) return null;
  return res.json();
}

// Auth
export async function login(username: string, password: string) {
  const data = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function signup(username: string, password: string) {
  return apiFetch("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe() {
  return apiFetch("/auth/me");
}

// Projects
export async function getProjects() {
  return apiFetch("/projects");
}

export async function getProject(id: string) {
  return apiFetch(`/projects/${id}`);
}

export async function createProject(name: string, description?: string) {
  return apiFetch("/projects", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function deleteProject(id: string) {
  return apiFetch(`/projects/${id}`, { method: "DELETE" });
}

// Documents
export async function uploadDocument(projectId: string, name: string) {
  return apiFetch(`/projects/${projectId}/documents`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function getDocumentContentUrl(projectId: string, documentId: string) {
  return apiFetch(`/projects/${projectId}/documents/${documentId}/content`);
}

export async function deleteDocument(projectId: string, documentId: string) {
  return apiFetch(`/projects/${projectId}/documents/${documentId}`, {
    method: "DELETE",
  });
}

// Members
export async function addMembers(projectId: string, usernames: string[]) {
  return apiFetch(`/projects/${projectId}/members`, {
    method: "POST",
    body: JSON.stringify({ usernames }),
  });
}

export async function removeMember(projectId: string, userId: string) {
  return apiFetch(`/projects/${projectId}/members/${userId}`, {
    method: "DELETE",
  });
}

// S3 upload
export async function uploadFileToS3(presignedUrl: { url: string; fields: Record<string, string> }, file: File) {
  const formData = new FormData();
  Object.entries(presignedUrl.fields).forEach(([key, value]) => {
    formData.append(key, value);
  });
  formData.append("file", file);

  const res = await fetch(presignedUrl.url, {
    method: "POST",
    body: formData,
  });

  if (!res.ok && res.status !== 204) {
    throw new Error("Failed to upload file to S3");
  }
}
