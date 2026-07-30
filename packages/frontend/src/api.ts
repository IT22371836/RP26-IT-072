import type {
  RecommendationResponse,
  Component4RankResponse,
  ProviderProfile,
  ProviderProfileInput,
  CustomerProfile,
  CustomerProfileUpdate,
  InteractionType,
  Interaction,
  ServiceRequest,
  ServiceRequestInput,
  TokenResponse,
  User,
  UserRole,
  AdminOverview,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? "Something went wrong. Please try again.", response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (role: Exclude<UserRole, "admin">, fullName: string, email: string, password: string) =>
    request<User>(`/auth/register/${role}`, {
      method: "POST",
      body: JSON.stringify({ full_name: fullName, email, password }),
    }),
  me: (token: string) => request<User>("/auth/me", {}, token),
  createServiceRequest: (payload: ServiceRequestInput, token: string) =>
    request<ServiceRequest>(
      "/service-requests",
      { method: "POST", body: JSON.stringify(payload) },
      token,
    ),
  listServiceRequests: (token: string) => request<ServiceRequest[]>("/service-requests/me", {}, token),
  recommend: (serviceRequest: ServiceRequest, token: string) =>
    request<RecommendationResponse>(
      "/component1/recommend",
      {
        method: "POST",
        body: JSON.stringify({
          request_id: serviceRequest.request_id,
          query: serviceRequest.request_text,
          category: serviceRequest.category,
          district: serviceRequest.district,
          city: serviceRequest.city,
          min_rating: 0,
          top_k: 20,
        }),
      },
      token,
    ),
  rankComponent4: (requestId: string, providerIds: string[], token: string) =>
    request<Component4RankResponse>(
      "/component4/rank",
      {
        method: "POST",
        body: JSON.stringify({
          request_id: requestId,
          provider_ids: providerIds,
          top_k: 5,
          force_recalculate: false,
        }),
      },
      token,
    ),
  getProviderProfile: (token: string) => request<ProviderProfile>("/providers/me", {}, token),
  createProviderProfile: (payload: ProviderProfileInput, token: string) =>
    request<ProviderProfile>(
      "/providers/me",
      { method: "POST", body: JSON.stringify(payload) },
      token,
    ),
  getCustomerProfile: (token: string) => request<CustomerProfile>("/customers/me", {}, token),
  updateCustomerProfile: (payload: CustomerProfileUpdate, token: string) =>
    request<CustomerProfile>(
      "/customers/me",
      { method: "PATCH", body: JSON.stringify(payload) },
      token,
    ),
  logInteraction: (
    payload: {
      request_id: string;
      provider_id: string;
      provider_name?: string;
      category: string;
      interaction_type: InteractionType;
      rating?: number;
    },
    token: string,
  ) =>
    request("/interactions", { method: "POST", body: JSON.stringify(payload) }, token),
  listInteractions: (token: string) => request<Interaction[]>("/interactions/me?limit=500", {}, token),
  listProviderInteractions: (token: string) =>
    request<Interaction[]>("/interactions/provider/me?limit=500", {}, token),
  completeBooking: (interactionId: string, token: string) =>
    request<Interaction>(`/interactions/${interactionId}/complete`, { method: "POST" }, token),
  cancelBooking: (interactionId: string, token: string) =>
    request<Interaction>(`/interactions/${interactionId}/cancel`, { method: "POST" }, token),
  rateBooking: (interactionId: string, rating: number, token: string) =>
    request<Interaction>(
      `/interactions/${interactionId}/rate`,
      { method: "POST", body: JSON.stringify({ rating }) },
      token,
    ),
  getAdminOverview: (token: string) => request<AdminOverview>("/admin/overview", {}, token),
  listAdminUsers: (token: string) => request<User[]>("/admin/users", {}, token),
  setUserActive: (userId: string, isActive: boolean, token: string) =>
    request<User>(
      `/admin/users/${userId}/status`,
      { method: "PATCH", body: JSON.stringify({ is_active: isActive }) },
      token,
    ),
  listAdminProviders: (token: string) => request<ProviderProfile[]>("/admin/providers", {}, token),
  listAdminRequests: (token: string) =>
    request<ServiceRequest[]>("/admin/service-requests", {}, token),
};
