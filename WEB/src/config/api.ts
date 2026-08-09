import { runtimeConfig } from './runtime';

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

export type PipelineStatus =
  | 'initializing' | 'created' | 'component1_running' | 'component1_completed'
  | 'component2_running' | 'component2_completed' | 'component4_running'
  | 'completed' | 'failed' | 'retry_pending' | 'cancelled';

export interface PipelineProviderDto {
  provider_id: string;
  provider_name: string;
  category: string;
  district: string;
  city: string;
  rank: number;
  hybrid_score?: number;
  tfidf_score?: number;
  bert_score?: number;
  cf_score?: number;
  final_score?: number;
  aspect_scores?: Record<string, number>;
  mean_credibility?: number;
  evidence_status?: string;
  platform_rating?: number;
  platform_review_count?: number;
}

export interface PipelineRunDto {
  run_id: string;
  request_id: string;
  user_id: string;
  status: PipelineStatus;
  request: Record<string, any>;
  component1: { providers: PipelineProviderDto[]; component_version: string; model_version: string } | null;
  component2: {
    output_results: Record<string, any>;
    all_evaluated_providers: Array<Record<string, any>>;
    component_version: string;
    model_version: string;
  } | null;
  component4: { providers: PipelineProviderDto[]; versions: Record<string, string> } | null;
  fallback: { used: boolean; fallback_reason: string; source: string } | null;
  error: { code: string; message: string; retryable: boolean } | null;
  selected_provider_id: string | null;
  booking_interaction_id: string | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface PipelineCreateDto {
  request_text: string;
  category: string;
  district: string;
  city: string;
  urgency: 'normal' | 'urgent' | 'emergency';
  service_date: string;
  service_time: { start_time: string; end_time: string };
  location_type: 'indoor' | 'outdoor' | 'indoor and outdoor';
}

export interface InteractionDto {
  interaction_id: string;
  request_id: string;
  user_id: string;
  provider_id: string;
  provider_name: string | null;
  category: string;
  interaction_type: string;
  rating: number | null;
  review_text: string | null;
  timestamp: string;
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
    credentials: 'omit',
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
    credentials: 'omit',
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
  },

  startPipeline(token: string, payload: PipelineCreateDto, idempotencyKey: string): Promise<{ run_id: string }> {
    return request<{ run_id: string }>('/pipeline/runs', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload)
    }, token);
  },

  getPipeline(token: string, runId: string): Promise<PipelineRunDto> {
    return request<PipelineRunDto>(`/pipeline/runs/${encodeURIComponent(runId)}`, {}, token);
  },

  listPipelines(token: string): Promise<PipelineRunDto[]> {
    return request<PipelineRunDto[]>('/pipeline/runs?limit=50', {}, token);
  },

  retryPipeline(token: string, runId: string): Promise<PipelineRunDto> {
    return request<PipelineRunDto>(`/pipeline/runs/${encodeURIComponent(runId)}/retry`, {
      method: 'POST'
    }, token);
  },

  selectPipelineProvider(token: string, runId: string, providerId: string): Promise<{ booking_interaction_id: string }> {
    return request<{ booking_interaction_id: string }>(
      `/pipeline/runs/${encodeURIComponent(runId)}/selection`,
      { method: 'POST', body: JSON.stringify({ provider_id: providerId }) },
      token
    );
  },

  listCustomerInteractions(token: string): Promise<InteractionDto[]> {
    return request<InteractionDto[]>('/interactions/me?limit=500', {}, token);
  },

  listProviderInteractions(token: string): Promise<InteractionDto[]> {
    return request<InteractionDto[]>('/interactions/provider/me?limit=500', {}, token);
  },

  completeBooking(token: string, interactionId: string): Promise<InteractionDto> {
    return request<InteractionDto>(`/interactions/${encodeURIComponent(interactionId)}/complete`, { method: 'POST' }, token);
  },

  cancelBooking(token: string, interactionId: string): Promise<InteractionDto> {
    return request<InteractionDto>(`/interactions/${encodeURIComponent(interactionId)}/cancel`, { method: 'POST' }, token);
  },

  rateBooking(token: string, interactionId: string, rating: number, reviewText: string): Promise<InteractionDto> {
    return request<InteractionDto>(`/interactions/${encodeURIComponent(interactionId)}/rate`, {
      method: 'POST',
      body: JSON.stringify({ rating, review_text: reviewText || null })
    }, token);
  }
};
