const API_BASE = "http://localhost:8000/api/v1";

// Maps form values → human-readable labels sent to backend
//front end details send to backend
const SERVICE_TYPE_LABELS: Record<string, string> = {
  plumbing: "Plumbing",
  electrical: "Electrical",
  cleaning: "Cleaning",
  carpentry: "Carpentry",
  painting: "Painting",
};

const SERVICE_ISSUE_LABELS: Record<string, string> = {
  leak: "Water Leak",
  repair: "Repair Needed",
  install: "Installation",
  maintenance: "Maintenance",
  inspection: "Inspection",
};

export type ServiceRequestPayload = {
  service_type: string;
  service_issue: string;
  location: {
    longitude: number;
    latitude: number;
  };
  date: string;
  time: string;
  service_env: string[];
};

export type WeatherInfo = {
  temperature_c: number;
  wind_speed_kmh: number;
  precipitation_mm: number;
  precipitation_probability_pct: number;
  condition: string;
  weather_code: number;
};

export type MatchedProvider = {
  provider_id: string;
  first_name: string;
  last_name: string;
  service_type: string;
  work_location: { latitude: number; longitude: number };
  home_address: string;
  available_hours: string;
  working_days: string;
  distance_km: number;
};

export type SuggestedWindow = {
  date: string;
  time: string;
  condition: string;
  temperature_c: number;
  precipitation_probability: number;
  risk_level: "SAFE" | "MODERATE" | "HIGH" | "EXTREME";
};

export type WeatherRisk = {
  risk_level: "SAFE" | "MODERATE" | "HIGH" | "EXTREME";
  risk_score: number;
  risk_reasons: string[];
  recommendation: string;
  suggested_windows: SuggestedWindow[];
};

export type ServiceRequestResponse = {
  id: string;
  message: string;
  weather: WeatherInfo | null;
  weather_risk: WeatherRisk | null;
  matched_providers: MatchedProvider[];
};

export type ServiceRequestFormState = {
  serviceType: string;
  serviceIssue: string;
  latitude: string;
  longitude: string;
  date: string;
  time: string;
  indoor: boolean;
  outdoor: boolean;
};

/** Converts raw form state into the API payload shape. */
export function buildServiceRequestPayload(form: ServiceRequestFormState): ServiceRequestPayload {
  const serviceEnv: string[] = [];
  if (form.indoor) serviceEnv.push("Indoor");
  if (form.outdoor) serviceEnv.push("Outdoor");

  return {
    service_type: SERVICE_TYPE_LABELS[form.serviceType] ?? form.serviceType,
    service_issue: SERVICE_ISSUE_LABELS[form.serviceIssue] ?? form.serviceIssue,
    location: {
      longitude: parseFloat(form.longitude),
      latitude: parseFloat(form.latitude),
    },
    date: form.date,
    time: form.time,
    service_env: serviceEnv,
  };
}

/** Submits a service request to the backend. */
export async function submitServiceRequest(
  form: ServiceRequestFormState
): Promise<ServiceRequestResponse> {
  const payload = buildServiceRequestPayload(form);
//backend details grap and send to frontend
  const response = await fetch(`${API_BASE}/service-requests/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to submit service request"
    );
  }

  return response.json() as Promise<ServiceRequestResponse>;
}
