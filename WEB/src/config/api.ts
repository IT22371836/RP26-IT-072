import { runtimeConfig } from './runtime';

export interface BackendUser {
  user_id: string;
  email: string;
  full_name: string;
  role: 'customer' | 'provider' | 'admin';
  is_active: boolean;
  created_at: string;
}

export interface BackendTokenResponse {
  access_token: string | null;
  token_type: 'bearer';
  expires_in: number;
  user: BackendUser;
  token_transport: 'bearer' | 'cookie';
}

export interface CustomerLocationDto {
  latitude: number;
  longitude: number;
}

export interface CustomerProfileDto {
  customer_id: string;
  user_id: string;
  phone: string | null;
  district: string | null;
  city: string | null;
  preferred_language: string;
  location: CustomerLocationDto | null;
  customer_image: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerProfileUpdateDto {
  phone?: string | null;
  district?: string | null;
  city?: string | null;
  preferred_language?: string | null;
  location?: CustomerLocationDto | null;
  customer_image?: string | null;
}

export interface ProviderDayScheduleDto {
  is_open: boolean;
  start: string;
  end: string;
}

export interface ProviderWorkingHoursDto {
  monday: ProviderDayScheduleDto;
  tuesday: ProviderDayScheduleDto;
  wednesday: ProviderDayScheduleDto;
  thursday: ProviderDayScheduleDto;
  friday: ProviderDayScheduleDto;
  saturday: ProviderDayScheduleDto;
  sunday: ProviderDayScheduleDto;
}

export type ProviderDocumentCategoryDto =
  | 'identity_document'
  | 'certification'
  | 'business_registration'
  | 'experience_proof'
  | 'portfolio_work';

export interface ProviderDocumentItemDto {
  file_id: string;
  file_name: string;
  file_url: string;
  legacy_url: string | null;
  current_url: string | null;
  storage_path: string | null;
  content_sha256: string | null;
  content_type: 'image/jpeg' | 'image/png' | 'application/pdf' | null;
  size_bytes: number | null;
  format: 'JPG' | 'PNG' | 'PDF';
  uploaded_at: string;
  deleted_at: string | null;
}

export interface ProviderDocumentsDto {
  status: boolean;
  verified: boolean;
  identity_document: ProviderDocumentItemDto[];
  certification: ProviderDocumentItemDto[];
  business_registration: ProviderDocumentItemDto[];
  experience_proof: ProviderDocumentItemDto[];
  portfolio_work: ProviderDocumentItemDto[];
}

export interface ProviderPrivateDto {
  provider_id: string;
  user_id: string;
  email: string | null;
  provider_name: string;
  category: string;
  district: string;
  city: string;
  experience_years: number;
  skills: string[];
  description: string;
  rating: number;
  review_count: number;
  booking_success_rate: number;
  interaction_count: number;
  phone: string | null;
  location: CustomerLocationDto | null;
  provider_image: string | null;
  preferred_language: string;
  nic: string | null;
  working_hours: ProviderWorkingHoursDto | null;
  verified: boolean;
  documents: ProviderDocumentsDto;
  created_at: string;
  updated_at: string;
}

export interface ProviderProfileUpdateDto {
  provider_name?: string | null;
  category?: string | null;
  district?: string | null;
  city?: string | null;
  experience_years?: number | null;
  skills?: string[] | null;
  description?: string | null;
  phone?: string | null;
  location?: CustomerLocationDto | null;
  provider_image?: string | null;
  preferred_language?: string | null;
  nic?: string | null;
  working_hours?: ProviderWorkingHoursDto | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${runtimeConfig.apiBaseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers
  });
  const contentType = response.headers.get('content-type') || '';
  const body: unknown = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = typeof body === 'object' && body !== null && 'detail' in body
      ? (body as { detail: unknown }).detail
      : body;
    const message = typeof detail === 'string' ? detail : `API request failed (${response.status})`;
    throw new ApiError(message, response.status, body);
  }
  return body as T;
}

async function requestBlob(path: string, token?: string): Promise<Blob> {
  const headers = new Headers({ Accept: 'image/jpeg, image/png, application/pdf' });
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${runtimeConfig.apiBaseUrl}${path}`, {
    credentials: 'include',
    headers
  });
  if (!response.ok) {
    const details = await response.json().catch(() => null);
    const message = details && typeof details === 'object' && 'detail' in details
      ? String(details.detail)
      : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, details);
  }
  return response.blob();
}

export const backendApi = {
  login(email: string, password: string): Promise<BackendTokenResponse> {
    return request<BackendTokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
  },

  linkFirebaseAccount(
    firebaseIdToken: string,
    newPassword: string
  ): Promise<BackendTokenResponse> {
    return request<BackendTokenResponse>('/auth/link/firebase', {
      method: 'POST',
      body: JSON.stringify({
        firebase_id_token: firebaseIdToken,
        new_password: newPassword
      })
    });
  },

  getCurrentUser(token?: string): Promise<BackendUser> {
    return request<BackendUser>('/auth/me', {}, token);
  },

  logout(): Promise<void> {
    return request<void>('/auth/logout', { method: 'POST' });
  },

  getCustomerProfile(token: string): Promise<CustomerProfileDto> {
    return request<CustomerProfileDto>('/customers/me', {}, token);
  },

  updateCustomerProfile(
    token: string,
    payload: CustomerProfileUpdateDto
  ): Promise<CustomerProfileDto> {
    return request<CustomerProfileDto>('/customers/me', {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }, token);
  },

  getProviderProfile(token: string): Promise<ProviderPrivateDto> {
    return request<ProviderPrivateDto>('/providers/me', {}, token);
  },

  updateProviderProfile(
    token: string,
    payload: ProviderProfileUpdateDto
  ): Promise<ProviderPrivateDto> {
    return request<ProviderPrivateDto>('/providers/me', {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }, token);
  },

  addProviderDocument(
    token: string,
    category: ProviderDocumentCategoryDto,
    payload: {
      file_id: string;
      file_name: string;
      file_url: string;
      format: 'JPG' | 'PNG' | 'PDF';
    }
  ): Promise<ProviderPrivateDto> {
    return request<ProviderPrivateDto>(`/providers/me/documents/${category}`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }, token);
  },

  uploadProviderDocument(
    token: string,
    category: ProviderDocumentCategoryDto,
    payload: { file_name: string; data_url: string }
  ): Promise<ProviderPrivateDto> {
    return request<ProviderPrivateDto>(`/providers/me/documents/${category}/upload`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }, token);
  },

  downloadProviderDocument(
    token: string,
    category: ProviderDocumentCategoryDto,
    fileId: string
  ): Promise<Blob> {
    return requestBlob(
      `/providers/me/documents/${category}/${encodeURIComponent(fileId)}/content`,
      token
    );
  },

  downloadAdminProviderDocument(
    token: string,
    providerId: string,
    category: ProviderDocumentCategoryDto,
    fileId: string
  ): Promise<Blob> {
    return requestBlob(
      `/admin/providers/${encodeURIComponent(providerId)}/documents/${category}/${encodeURIComponent(fileId)}/content`,
      token
    );
  },

  deleteProviderDocument(
    token: string,
    category: ProviderDocumentCategoryDto,
    fileId: string
  ): Promise<ProviderPrivateDto> {
    return request<ProviderPrivateDto>(
      `/providers/me/documents/${category}/${encodeURIComponent(fileId)}`,
      { method: 'DELETE' },
      token
    );
  },

  requestProviderDocumentVerification(token: string): Promise<ProviderPrivateDto> {
    return request<ProviderPrivateDto>('/providers/me/request-document-verification', {
      method: 'POST'
    }, token);
  },

  listAdminProviders(token: string): Promise<ProviderPrivateDto[]> {
    return request<ProviderPrivateDto[]>('/admin/providers', {}, token);
  },

  setAdminProviderVerification(
    token: string,
    providerId: string,
    verified: boolean,
    reason: string
  ): Promise<ProviderPrivateDto> {
    return request<ProviderPrivateDto>(
      `/admin/providers/${encodeURIComponent(providerId)}/verification`,
      {
        method: 'PATCH',
        body: JSON.stringify({ verified, reason })
      },
      token
    );
  }
};
