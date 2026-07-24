import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { ServiceRequestResponse, MatchedProvider, WeatherRisk, SuggestedWindow } from "../api/serviceRequestApi";
import { submitServiceRequest } from "../api/serviceRequestApi";
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

const RISK_CONFIG: Record<WeatherRisk["risk_level"], { color: string; bg: string; border: string; icon: string; label: string }> = {
  SAFE:     { color: "#10b981", bg: "rgba(16,185,129,0.08)",  border: "rgba(16,185,129,0.3)",  icon: "✅", label: "Safe Conditions"   },
  MODERATE: { color: "#f59e0b", bg: "rgba(245,158,11,0.08)",  border: "rgba(245,158,11,0.3)",  icon: "⚠️", label: "Moderate Risk"    },
  HIGH:     { color: "#f97316", bg: "rgba(249,115,22,0.08)",  border: "rgba(249,115,22,0.3)",  icon: "🚨", label: "High Risk"        },
  EXTREME:  { color: "#ef4444", bg: "rgba(239,68,68,0.08)",   border: "rgba(239,68,68,0.3)",   icon: "⛔", label: "Extreme Risk"    },
};

function WeatherRiskCard({
  risk,
  onSearchProviders,
  isRefetching,
  selectedWindowKey,
}: {
  risk: WeatherRisk;
  onSearchProviders: (date: string, time: string) => void;
  isRefetching: boolean;
  selectedWindowKey: string | null;
}) {
  const cfg = RISK_CONFIG[risk.risk_level];
  return (
    <div
      className="results-card results-card--risk"
      style={{ borderColor: cfg.border, background: `linear-gradient(135deg, ${cfg.bg} 0%, var(--bg-surface) 100%)` }}
    >
      <h2 className="results-card__title" style={{ color: cfg.color }}>
        Weather Risk Advisory
      </h2>

      {/* Risk level badge */}
      <div className="risk-badge" style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}>
        <span className="risk-badge__icon">{cfg.icon}</span>
        <div className="risk-badge__text">
          <span className="risk-badge__label" style={{ color: cfg.color }}>{cfg.label}</span>
          <span className="risk-badge__score" style={{ color: cfg.color }}>
            Risk Score: {risk.risk_score.toFixed(0)} / 100
          </span>
        </div>
      </div>

      {/* Score bar */}
      <div className="risk-score-bar">
        <div
          className="risk-score-bar__fill"
          style={{ width: `${risk.risk_score}%`, background: cfg.color }}
        />
      </div>

      {/* Reasons */}
      {risk.risk_reasons.length > 0 && (
        <ul className="risk-reasons">
          {risk.risk_reasons.map((reason, i) => (
            <li key={i} className="risk-reason-item" style={{ borderLeftColor: cfg.color }}>
              {reason}
            </li>
          ))}
        </ul>
      )}

      {/* Recommendation */}
      <p className="risk-recommendation">{risk.recommendation}</p>

      {/* Suggested windows */}
      {risk.suggested_windows.length > 0 && (
        <div className="risk-windows">
          <p className="risk-windows__title">Safer Time Windows</p>
          {risk.suggested_windows.map((w: SuggestedWindow, i: number) => {
            const wCfg = RISK_CONFIG[w.risk_level];
            const windowKey = `${w.date}T${w.time}`;
            const isActive = selectedWindowKey === windowKey;
            const isLoading = isRefetching && isActive;
            return (
              <div
                key={i}
                className={`risk-window-item${isActive ? " risk-window-item--active" : ""}`}
                style={isActive ? { borderColor: wCfg.color } : undefined}
              >
                <div className="risk-window-item__left">
                  <span className="risk-window-item__date">{formatDate(w.date)}</span>
                  <span className="risk-window-item__time">at {w.time}</span>
                  <span className="risk-window-item__condition">{w.condition}</span>
                  <div className="risk-window-item__meta">
                    <span className="risk-window-item__rain">{w.precipitation_probability}% rain</span>
                    <span
                      className="risk-window-item__badge"
                      style={{ background: wCfg.bg, color: wCfg.color, border: `1px solid ${wCfg.border}` }}
                    >
                      {wCfg.label}
                    </span>
                  </div>
                </div>
                <button
                  className="risk-window-search-btn"
                  style={{ borderColor: wCfg.color, color: isActive ? "#fff" : wCfg.color, background: isActive ? wCfg.color : "transparent" }}
                  disabled={isRefetching}
                  onClick={() => onSearchProviders(w.date, w.time)}
                >
                  {isLoading ? (
                    <span className="risk-window-search-btn__spinner" />
                  ) : isActive ? (
                    "✓ Active"
                  ) : (
                    "Search Providers"
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
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

  // Active provider list — starts from the initial response, updated when a window is searched
  const [activeProviders, setActiveProviders] = useState<MatchedProvider[]>(
    state?.response.matched_providers ?? []
  );
  // Which window is currently selected — "YYYY-MM-DDThh:mm" or null (original)
  const [selectedWindowKey, setSelectedWindowKey] = useState<string | null>(null);
  // The date/time shown in the providers header
  const [activeSlot, setActiveSlot] = useState<{ date: string; time: string } | null>(null);
  const [isRefetching, setIsRefetching] = useState(false);
  const [refetchError, setRefetchError] = useState<string | null>(null);

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

  async function handleWindowSearch(date: string, time: string) {
    const windowKey = `${date}T${time}`;
    // Clicking an already-active window resets to the original results
    if (selectedWindowKey === windowKey) {
      setActiveProviders(response.matched_providers);
      setSelectedWindowKey(null);
      setActiveSlot(null);
      setRefetchError(null);
      return;
    }

    setIsRefetching(true);
    setSelectedWindowKey(windowKey);
    setRefetchError(null);

    try {
      const result = await submitServiceRequest({
        serviceType: formSummary.serviceType,
        serviceIssue: formSummary.serviceIssue,
        latitude: formSummary.latitude,
        longitude: formSummary.longitude,
        date,
        time,
        indoor: formSummary.indoor,
        outdoor: formSummary.outdoor,
      });
      setActiveProviders(result.matched_providers);
      setActiveSlot({ date, time });
    } catch (err: unknown) {
      setRefetchError(err instanceof Error ? err.message : "Failed to fetch providers for this slot.");
      // revert selection on error
      setSelectedWindowKey(null);
    } finally {
      setIsRefetching(false);
    }
  }

  function handleResetToOriginal() {
    setActiveProviders(response.matched_providers);
    setSelectedWindowKey(null);
    setActiveSlot(null);
    setRefetchError(null);
  }

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
            Found <strong>{activeProviders.length}</strong> provider
            {activeProviders.length !== 1 ? "s" : ""} matching your criteria
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
                <span className="summary-value">{formatDate(activeSlot?.date ?? formSummary.date)}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">Time</span>
                <span className="summary-value">{activeSlot?.time ?? formSummary.time}</span>
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
                    {formatDate(activeSlot?.date ?? formSummary.date)} —{" "}
                    <strong>{getDayType(activeSlot?.date ?? formSummary.date)}</strong>
                  </span>
                </div>
              </li>
              <li className="criteria-item criteria-item--match">
                <span className="criteria-icon">✓</span>
                <div>
                  <span className="criteria-label">Available Hours</span>
                  <span className="criteria-detail">
                    Providers whose hours cover <strong>{activeSlot?.time ?? formSummary.time}</strong>
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

          {/* Weather Risk Advisory (outdoor only) */}
          {response.weather_risk && (
            <WeatherRiskCard
              risk={response.weather_risk}
              onSearchProviders={handleWindowSearch}
              isRefetching={isRefetching}
              selectedWindowKey={selectedWindowKey}
            />
          )}
        </aside>

        {/* Right column: matched providers */}
        <main className="results-main">
          <div className="results-providers-header">
            <div className="results-providers-title-row">
              <h2 className="results-providers-title">
                Matched Providers
                <span className="results-providers-count">{activeProviders.length}</span>
              </h2>
              {activeSlot && (
                <button className="results-reset-btn" onClick={handleResetToOriginal}>
                  ← Back to original time
                </button>
              )}
            </div>
            {activeSlot ? (
              <p className="results-providers-hint results-providers-hint--alt">
                Showing providers available on{" "}
                <strong>{formatDate(activeSlot.date)}</strong> at <strong>{activeSlot.time}</strong>
              </p>
            ) : (
              activeProviders.length > 0 && (
                <p className="results-providers-hint">Sorted by distance from your location</p>
              )
            )}
            {refetchError && (
              <p className="results-providers-error">{refetchError}</p>
            )}
          </div>

          {isRefetching ? (
            <div className="results-providers-loading">
              <span className="results-providers-loading__spinner" />
              <span>Finding providers for new time slot…</span>
            </div>
          ) : activeProviders.length === 0 ? (
            <div className="results-no-providers">
              <p className="results-no-providers__icon">😕</p>
              <p className="results-no-providers__title">No providers available</p>
              <p className="results-no-providers__text">
                No providers matched your selected service type, date, and time. Try adjusting
                the date or time and submit a new request.
              </p>
              {activeSlot && (
                <button className="results-back-btn results-back-btn--center" onClick={handleResetToOriginal}>
                  Back to original time
                </button>
              )}
              <button
                className="results-back-btn results-back-btn--center"
                onClick={() => navigate("/customer/check-provider")}
              >
                Try Again
              </button>
            </div>
          ) : (
            <div className="providers-list">
              {activeProviders.map((p, i) => (
                <ProviderCard key={p.provider_id} provider={p} index={i} />
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
