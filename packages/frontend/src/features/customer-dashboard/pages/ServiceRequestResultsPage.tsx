import { useLocation, useNavigate } from "react-router-dom";
import type { ServiceRequestResponse, MatchedProvider } from "../api/serviceRequestApi";
import "./ServiceRequestResultsPage.css";

type FormSummary = {
  serviceType: string;
  serviceIssue: string;
  date: string;
  time: string;
  indoor: boolean;
  outdoor: boolean;
  latitude: string;
  longitude: string;
  locationName: string;
};

type ResultsState = {
  response: ServiceRequestResponse;
  formSummary: FormSummary;
};

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

const SERVICE_ICONS: Record<string, string> = {
  plumbing: "🔧",
  electrical: "⚡",
  cleaning: "🧹",
  carpentry: "📐",
  painting: "🎨",
};

const WORKING_DAY_BADGE: Record<string, { label: string; cls: string }> = {
  "whole week": { label: "Whole Week", cls: "badge-green" },
  "weekdays only": { label: "Weekdays", cls: "badge-blue" },
  "weekends only": { label: "Weekends", cls: "badge-purple" },
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

function getDayType(dateStr: string): string {
  const day = new Date(dateStr + "T00:00:00").getDay(); // 0=Sun, 6=Sat
  return day === 0 || day === 6 ? "Weekend" : "Weekday";
}

function ProviderCard({ provider, index }: { provider: MatchedProvider; index: number }) {
  const badge = WORKING_DAY_BADGE[provider.working_days.toLowerCase()] ?? { label: provider.working_days, cls: "badge-gray" };

  return (
    <div className={`provider-card ${index === 0 ? "provider-card--closest" : ""}`}>
      {index === 0 && <div className="provider-card__closest-tag">Nearest</div>}
      <div className="provider-card__header">
        <div className="provider-card__avatar">
          {provider.first_name[0]}{provider.last_name[0]}
        </div>
        <div className="provider-card__identity">
          <span className="provider-card__name">
            {provider.first_name} {provider.last_name}
          </span>
          <span className="provider-card__id">{provider.provider_id}</span>
        </div>
        <div className="provider-card__distance">
          <span className="provider-card__distance-value">{provider.distance_km}</span>
          <span className="provider-card__distance-unit">km away</span>
        </div>
      </div>

      <div className="provider-card__details">
        <div className="provider-detail-row">
          <span className="provider-detail-icon">📍</span>
          <span className="provider-detail-text">{provider.home_address}</span>
        </div>
        <div className="provider-detail-row">
          <span className="provider-detail-icon">🕐</span>
          <span className="provider-detail-text">{provider.available_hours}</span>
        </div>
        <div className="provider-detail-row">
          <span className="provider-detail-icon">📅</span>
          <span className={`provider-day-badge ${badge.cls}`}>{badge.label}</span>
        </div>
      </div>
    </div>
  );
}

export function ServiceRequestResultsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as ResultsState | null;

  if (!state) {
    return (
      <div className="results-page">
        <div className="results-no-data">
          <p>No results to display.</p>
          <button className="results-back-btn" onClick={() => navigate("/customer/check-provider")}>
            Back to Request Form
          </button>
        </div>
      </div>
    );
  }

  const { response, formSummary } = state;
  const dayType = getDayType(formSummary.date);
  const envLabel = [formSummary.indoor && "Indoor", formSummary.outdoor && "Outdoor"].filter(Boolean).join(" & ");

  return (
    <div className="results-page">
      {/* Header */}
      <div className="results-header">
        <button className="results-back-btn" onClick={() => navigate("/customer/check-provider")}>
          ← New Request
        </button>
        <div className="results-header__title-block">
          <h1 className="results-title">Service Request Results</h1>
          <p className="results-subtitle">
            
            Found <strong>{response.matched_providers.length}</strong> provider
            {response.matched_providers.length !== 1 ? "s" : ""} matching your criteria
          </p>
        </div>
        <span className="results-request-id">#{response.id.slice(-8).toUpperCase()}</span>
      </div>

      <div className="results-body">
        {/* Left column: request summary + matching criteria + weather */}
        <aside className="results-sidebar">
          {/* Request Summary */}
          <div className="results-card">
            <h2 className="results-card__title">Your Request</h2>
            <div className="summary-grid">
              <div className="summary-item">
                <span className="summary-label">Service Type</span>
                <span className="summary-value">
                  {SERVICE_ICONS[formSummary.serviceType] ?? ""}{" "}
                  {SERVICE_TYPE_LABELS[formSummary.serviceType] ?? formSummary.serviceType}
                </span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Issue</span>
                <span className="summary-value">
                  {SERVICE_ISSUE_LABELS[formSummary.serviceIssue] ?? formSummary.serviceIssue}
                </span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Date</span>
                <span className="summary-value">{formatDate(formSummary.date)}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Time</span>
                <span className="summary-value">{formSummary.time}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Environment</span>
                <span className="summary-value">{envLabel}</span>
              </div>
              {formSummary.locationName && (
                <div className="summary-item">
                  <span className="summary-label">Location</span>
                  <span className="summary-value">{formSummary.locationName}</span>
                </div>
              )}
              <div className="summary-item">
                <span className="summary-label">Coordinates</span>
                <span className="summary-value summary-value--mono">
                  {parseFloat(formSummary.latitude).toFixed(4)}, {parseFloat(formSummary.longitude).toFixed(4)}
                </span>
              </div>
            </div>
          </div>

          {/* Matching Criteria */}
          <div className="results-card">
            <h2 className="results-card__title">Matching Criteria Used</h2>
            <ul className="criteria-list">
              <li className="criteria-item criteria-item--match">
                <span className="criteria-icon">✓</span>
                <div>
                  <span className="criteria-label">Service Type</span>
                  <span className="criteria-detail">
                    {SERVICE_TYPE_LABELS[formSummary.serviceType] ?? formSummary.serviceType}
                  </span>
                </div>
              </li>
              <li className="criteria-item criteria-item--match">
                <span className="criteria-icon">✓</span>
                <div>
                  <span className="criteria-label">Day of Week</span>
                  <span className="criteria-detail">
                    {formatDate(formSummary.date)} — <strong>{dayType}</strong>
                  </span>
                </div>
              </li>
              <li className="criteria-item criteria-item--match">
                <span className="criteria-icon">✓</span>
                <div>
                  <span className="criteria-label">Available Hours</span>
                  <span className="criteria-detail">
                    Providers whose hours cover <strong>{formSummary.time}</strong>
                  </span>
                </div>
              </li>
            </ul>
          </div>

          {/* Weather Card (outdoor only) */}
          {response.weather && (
            <div className="results-card results-card--weather">
              <h2 className="results-card__title">Weather Forecast</h2>
              <p className="weather-condition">{response.weather.condition}</p>
              <div className="weather-grid">
                <div className="weather-item">
                  <span className="weather-label">Temperature</span>
                  <span className="weather-value">{response.weather.temperature_c.toFixed(1)} °C</span>
                </div>
                <div className="weather-item">
                  <span className="weather-label">Rain Chance</span>
                  <span className="weather-value">{response.weather.precipitation_probability_pct}%</span>
                </div>
                <div className="weather-item">
                  <span className="weather-label">Precipitation</span>
                  <span className="weather-value">{response.weather.precipitation_mm} mm</span>
                </div>
                <div className="weather-item">
                  <span className="weather-label">Wind Speed</span>
                  <span className="weather-value">{response.weather.wind_speed_kmh} km/h</span>
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* Right column: matched providers */}
        <main className="results-main">
          <div className="results-providers-header">
            <h2 className="results-providers-title">
              Matched Providers
              <span className="results-providers-count">{response.matched_providers.length}</span>
            </h2>
            {response.matched_providers.length > 0 && (
              <p className="results-providers-hint">Sorted by distance from your location</p>
            )}
          </div>

          {response.matched_providers.length === 0 ? (
            <div className="results-no-providers">
              <p className="results-no-providers__icon">😕</p>
              <p className="results-no-providers__title">No providers available</p>
              <p className="results-no-providers__text">
                No providers matched your selected service type, date, and time. Try adjusting
                the date or time and submit a new request.
              </p>
              <button
                className="results-back-btn results-back-btn--center"
                onClick={() => navigate("/customer/check-provider")}
              >
                Try Again
              </button>
            </div>
          ) : (
            <div className="providers-list">
              {response.matched_providers.map((p, i) => (
                <ProviderCard key={p.provider_id} provider={p} index={i} />
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
