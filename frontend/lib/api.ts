/**
 * API client for RentWise backend
 */

import type {
  Candidate,
  CandidateContactPlan,
  ComparisonResponse,
  CreateProjectRequest,
  Dashboard,
  InvestigationResponse,
  Project,
  Token,
  UpdateCandidateRequest,
  UpdateProjectRequest,
  User,
} from "@/lib/types";

function normalizeApiBase(value: string | undefined): string {
  let normalized = value?.trim() || "http://localhost:8000";

  if (normalized.startsWith("NEXT_PUBLIC_API_URL=")) {
    normalized = normalized.slice("NEXT_PUBLIC_API_URL=".length).trim();
  }

  if (normalized.startsWith("https:/") && !normalized.startsWith("https://")) {
    normalized = normalized.replace(/^https:\//, "https://");
  }

  if (normalized.startsWith("http:/") && !normalized.startsWith("http://")) {
    normalized = normalized.replace(/^http:\//, "http://");
  }

  return normalized.replace(/\/+$/, "");
}

const API_BASE = normalizeApiBase(process.env.NEXT_PUBLIC_API_URL);

async function parseJsonSafely(res: Response) {
  const text = await res.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as { detail?: string };
  } catch {
    return null;
  }
}

function buildHeaders(token?: string, includeJson = false): HeadersInit {
  return {
    ...(includeJson ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function handleApiResponse<T>(
  res: Response,
  fallbackMessage: string
): Promise<T> {
  if (res.status === 204) {
    return undefined as T;
  }

  if (!res.ok) {
    const error = await parseJsonSafely(res);
    throw new Error(error?.detail || fallbackMessage);
  }

  return (await res.json()) as T;
}

function withNetworkErrorMessage(error: unknown, action: string): never {
  if (error instanceof TypeError) {
    throw new Error(
      `Unable to reach the backend while trying to ${action}. Check that the API server is running at ${API_BASE}.`
    );
  }

  throw error;
}

async function apiRequest<T>(
  path: string,
  options: RequestInit,
  fallbackMessage: string,
  action: string
): Promise<T> {
  let res: Response;

  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch (error) {
    withNetworkErrorMessage(error, action);
  }

  return await handleApiResponse<T>(res, fallbackMessage);
}

// ============== Auth ==============

export async function register(
  email: string,
  password: string
): Promise<Token> {
  return apiRequest<Token>(
    "/api/v1/auth/register",
    {
      method: "POST",
      headers: buildHeaders(undefined, true),
      body: JSON.stringify({ email, password }),
    },
    "Registration failed",
    "register"
  );
}

export async function login(
  email: string,
  password: string
): Promise<Token> {
  return apiRequest<Token>(
    "/api/v1/auth/login",
    {
      method: "POST",
      headers: buildHeaders(undefined, true),
      body: JSON.stringify({ email, password }),
    },
    "Login failed",
    "log in"
  );
}

export async function getCurrentUser(token: string): Promise<User> {
  return apiRequest<User>(
    "/api/v1/auth/me",
    { headers: buildHeaders(token) },
    "Failed to get user",
    "load your account"
  );
}

// ============== Projects ==============

export async function createProject(
  token: string,
  data: CreateProjectRequest
): Promise<Project> {
  return apiRequest<Project>(
    "/api/v1/projects",
    {
      method: "POST",
      headers: buildHeaders(token, true),
      body: JSON.stringify(data),
    },
    "Failed to create project",
    "create a project"
  );
}

export async function getProjects(token: string): Promise<{
  projects: Project[];
  total: number;
}> {
  return apiRequest<{ projects: Project[]; total: number }>(
    "/api/v1/projects",
    { headers: buildHeaders(token) },
    "Failed to get projects",
    "load projects"
  );
}

export async function getProject(
  token: string,
  projectId: string
): Promise<Project> {
  return apiRequest<Project>(
    `/api/v1/projects/${projectId}`,
    { headers: buildHeaders(token) },
    "Failed to get project",
    "load the project"
  );
}

export async function updateProject(
  token: string,
  projectId: string,
  data: UpdateProjectRequest
): Promise<Project> {
  return apiRequest<Project>(
    `/api/v1/projects/${projectId}`,
    {
      method: "PUT",
      headers: buildHeaders(token, true),
      body: JSON.stringify(data),
    },
    "Failed to update project",
    "update the project"
  );
}

export async function deleteProject(token: string, projectId: string): Promise<void> {
  return apiRequest<void>(
    `/api/v1/projects/${projectId}`,
    {
      method: "DELETE",
      headers: buildHeaders(token),
    },
    "Failed to delete project",
    "delete the project"
  );
}

// ============== Candidates ==============

export async function importCandidate(
  token: string,
  projectId: string,
  data: {
    name?: string;
    source_type?: string;
    raw_listing_text?: string;
    raw_chat_text?: string;
    raw_note_text?: string;
    uploaded_images?: File[];
  }
): Promise<Candidate> {
  const formData = new FormData();
  if (data.name) formData.append("name", data.name);
  if (data.source_type) formData.append("source_type", data.source_type);
  if (data.raw_listing_text) formData.append("raw_listing_text", data.raw_listing_text);
  if (data.raw_chat_text) formData.append("raw_chat_text", data.raw_chat_text);
  if (data.raw_note_text) formData.append("raw_note_text", data.raw_note_text);
  for (const image of data.uploaded_images || []) {
    formData.append("uploaded_images", image);
  }

  return apiRequest<Candidate>(
    `/api/v1/projects/${projectId}/candidates/import`,
    {
      method: "POST",
      headers: buildHeaders(token),
      body: formData,
    },
    "Failed to import candidate",
    "import a candidate"
  );
}

export async function getCandidates(
  token: string,
  projectId: string
): Promise<{ candidates: Candidate[]; total: number }> {
  return apiRequest<{ candidates: Candidate[]; total: number }>(
    `/api/v1/projects/${projectId}/candidates`,
    { headers: buildHeaders(token) },
    "Failed to get candidates",
    "load candidates"
  );
}

export async function getCandidate(
  token: string,
  projectId: string,
  candidateId: string
): Promise<Candidate> {
  return apiRequest<Candidate>(
    `/api/v1/projects/${projectId}/candidates/${candidateId}`,
    { headers: buildHeaders(token) },
    "Failed to get candidate",
    "load the candidate"
  );
}

export async function updateCandidate(
  token: string,
  projectId: string,
  candidateId: string,
  data: UpdateCandidateRequest
): Promise<Candidate> {
  return apiRequest<Candidate>(
    `/api/v1/projects/${projectId}/candidates/${candidateId}`,
    {
      method: "PUT",
      headers: buildHeaders(token, true),
      body: JSON.stringify(data),
    },
    "Failed to update candidate",
    "update the candidate"
  );
}

export async function reassessCandidate(
  token: string,
  projectId: string,
  candidateId: string
): Promise<Candidate> {
  return apiRequest<Candidate>(
    `/api/v1/projects/${projectId}/candidates/${candidateId}/reassess`,
    {
      method: "POST",
      headers: buildHeaders(token),
    },
    "Failed to reassess candidate",
    "reassess the candidate"
  );
}

export async function shortlistCandidate(
  token: string,
  projectId: string,
  candidateId: string
): Promise<Candidate> {
  return apiRequest<Candidate>(
    `/api/v1/projects/${projectId}/candidates/${candidateId}/shortlist`,
    {
      method: "POST",
      headers: buildHeaders(token),
    },
    "Failed to shortlist candidate",
    "shortlist the candidate"
  );
}

export async function rejectCandidate(
  token: string,
  projectId: string,
  candidateId: string
): Promise<Candidate> {
  return apiRequest<Candidate>(
    `/api/v1/projects/${projectId}/candidates/${candidateId}/reject`,
    {
      method: "POST",
      headers: buildHeaders(token),
    },
    "Failed to reject candidate",
    "reject the candidate"
  );
}

export async function deleteCandidate(
  token: string,
  projectId: string,
  candidateId: string
): Promise<void> {
  return apiRequest<void>(
    `/api/v1/projects/${projectId}/candidates/${candidateId}`,
    {
      method: "DELETE",
      headers: buildHeaders(token),
    },
    "Failed to delete candidate",
    "delete the candidate"
  );
}

export async function generateCandidateContactPlan(
  token: string,
  projectId: string,
  candidateId: string
): Promise<CandidateContactPlan> {
  return apiRequest<CandidateContactPlan>(
    `/api/v1/projects/${projectId}/candidates/${candidateId}/contact-plan`,
    {
      method: "POST",
      headers: buildHeaders(token),
    },
    "Failed to generate the contact plan",
    "generate a contact plan"
  );
}

// ============== Dashboard ==============

export async function getDashboard(
  token: string,
  projectId: string
): Promise<Dashboard> {
  return apiRequest<Dashboard>(
    `/api/v1/projects/${projectId}/dashboard`,
    { headers: buildHeaders(token) },
    "Failed to get dashboard",
    "load the dashboard"
  );
}

// ============== Investigation ==============

export async function runInvestigation(
  token: string,
  projectId: string
): Promise<InvestigationResponse> {
  return apiRequest<InvestigationResponse>(
    `/api/v1/projects/${projectId}/investigation/run`,
    {
      method: "POST",
      headers: buildHeaders(token),
    },
    "Failed to run investigation",
    "run investigation"
  );
}

// ============== Comparison ==============

export async function compareCandidates(
  token: string,
  projectId: string,
  candidateIds: string[]
): Promise<ComparisonResponse> {
  return apiRequest<ComparisonResponse>(
    `/api/v1/projects/${projectId}/compare`,
    {
      method: "POST",
      headers: buildHeaders(token, true),
      body: JSON.stringify({ candidate_ids: candidateIds }),
    },
    "Failed to compare candidates",
    "compare candidates"
  );
}
