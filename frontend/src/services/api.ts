/**
 * Centralized API client for RANN Web IDE
 * 
 * Handles HTTP requests with cookie-based authentication.
 * All requests are relative to NEXT_PUBLIC_API_URL or default to localhost.
 */

// Base URL from environment
declare const NEXT_PUBLIC_API_URL: string | undefined;
const API_BASE_URL = NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Project {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface FileContentResponse {
  path: string;
  content: string;
  language: string;
  size: number;
}

// Helper for cookie-based requests
function getApiUrl(path: string): string {
  // Remove leading slash and construct full URL
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${API_BASE_URL}/${cleanPath}`;
}

// Helper for authenticated requests with credentials
async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(getApiUrl(path), {
    credentials: 'include', // Include cookies for auth
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Project API
export const ProjectAPI = {
  async list(): Promise<Project[]> {
    return apiRequest<Project[]>('/api/projects');
  },

  async get(projectId: string): Promise<Project> {
    return apiRequest<Project>(`/api/projects/${projectId}`);
  },

  async create(name: string): Promise<Project> {
    return apiRequest<Project>('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  },

  async update(projectId: string, name: string): Promise<{ success: boolean }> {
    return apiRequest<{ success: boolean }>(`/api/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
  },

  async delete(projectId: string): Promise<{ success: boolean; message: string }> {
    return apiRequest<{ success: boolean; message: string }>(`/api/projects/${projectId}`, {
      method: 'DELETE',
    });
  },
};

// Auth API
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: { id: string; email: string };
}

export interface RegisterResponse {
  id: string;
  email: string;
  created_at: string;
}

export const AuthAPI = {
  async register(email: string, password: string): Promise<RegisterResponse> {
    return apiRequest<RegisterResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async login(email: string, password: string): Promise<LoginResponse> {
    return apiRequest<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async logout(): Promise<void> {
    await apiRequest('/auth/logout', { method: 'POST' });
  },

  async me(): Promise<{ id: string; email: string }> {
    return apiRequest<{ id: string; email: string }>('/auth/me');
  },
};

// File API
interface FileWriteParams {
  path: string;
  content: string;
}

export const FileAPI = {
  async write(projectId: string, params: FileWriteParams): Promise<{ success: boolean }> {
    return apiRequest<{ success: boolean }>(`/api/projects/${projectId}/files/content`, {
      method: 'PUT',
      body: JSON.stringify(params),
    });
  },

  async read(projectId: string, path: string): Promise<FileContentResponse> {
    return apiRequest<FileContentResponse>(`/api/projects/${projectId}/files/content`, {
      method: 'GET',
    });
  },
};

export default {
  ProjectAPI,
  AuthAPI,
  FileAPI,
};