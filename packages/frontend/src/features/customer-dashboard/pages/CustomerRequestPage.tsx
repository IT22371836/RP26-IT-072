import { useState } from "react";
import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./CustomerRequestPage.css";
import { submitServiceRequest } from "../api/serviceRequestApi";
import type { WeatherInfo } from "../api/serviceRequestApi";

// Fix for Leaflet default icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

// Map click handler component
function MapClickHandler({ onLocationSelect }: { onLocationSelect: (lat: string, lng: string) => void }) {
  useMapEvents({
    click(e: any) {
      onLocationSelect(e.latlng.lat.toFixed(4), e.latlng.lng.toFixed(4));
    },
  });
  return null;
}

export function CustomerRequestPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    serviceType: "",
    serviceIssue: "",
    latitude: "6.9271",
    longitude: "80.7744",
    locationName: "",
    date: "",
    time: "",
    urgency: "normal",
    indoor: false,
    outdoor: false,
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [mapKey, setMapKey] = useState(0);
  const [showMap, setShowMap] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [weatherResult, setWeatherResult] = useState<WeatherInfo | null>(null);

  const handleChange = (e: any) => {
    const { name, value, type, checked } = e.target;
    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  };

  const handleLocationSelect = (lat: string, lng: string) => {
    setForm({ ...form, latitude: lat, longitude: lng, locationName: "Selected on Map" });
    setMapKey((k) => k + 1);
  };

  const handleSearchLocation = async () => {
    if (!searchQuery) return;

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${searchQuery},Sri Lanka&format=json&limit=5`
      );
      //show results in the dropdown
      const results = await response.json();
      setSearchResults(results);
    } catch (error) {
      console.error("Search error:", error);
      setSearchResults([]);
    }
  };

  const handleSelectSearchResult = (result: any) => {
    setForm({
      ...form,
      latitude: result.lat,
      longitude: result.lon,
      locationName: result.display_name.split(",")[0],
    });
    setSearchResults([]);
    setSearchQuery("");
    setMapKey((k) => k + 1);
  };

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(false);
    setWeatherResult(null);
    try {
      //place where calls the API with user requested provider dataa
      const response = await submitServiceRequest(form);
      setSubmitSuccess(true);
      if (response.weather) setWeatherResult(response.weather);
      // Navigate to results page, passing full response + original form values
      navigate("/customer/service-request-results", {
        state: {
          response,
          formSummary: {
            serviceType: form.serviceType,
            serviceIssue: form.serviceIssue,
            date: form.date,
            time: form.time,
            indoor: form.indoor,
            outdoor: form.outdoor,
            latitude: form.latitude,
            longitude: form.longitude,
            locationName: form.locationName,
          },
        },
      });
    } catch (err: any) {
      setSubmitError(err.message ?? "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };
// validation for display the submit button
  const isFormValid = form.serviceType && form.serviceIssue && form.latitude && form.date && form.time && (form.indoor || form.outdoor);

  return (
    <div className="customer-request-page">
      <div className="customer-request-header">
        <h1>Find Your Service Provider</h1>
        <p>Fill in your service requirements and we'll find the perfect provider for you</p>
      </div>

      <form onSubmit={handleSubmit} style={styles.form}>
        {/* Service Type Section */}
        <div style={styles.section}>
          <h3 className="section-title">Service Information</h3>
          <div style={styles.gridTwo}>
            <div style={styles.formGroup}>
              <label className="form-label">Service Type *</label>
              <select name="serviceType" value={form.serviceType} onChange={handleChange} className="form-select">
                <option value="">Select a service type</option>
                <option value="plumbing">🔧 Plumbing</option>
                <option value="electrical">⚡ Electrical</option>
                <option value="cleaning">🧹 Cleaning</option>
                <option value="carpentry">📐 Carpentry</option>
                <option value="painting">🎨 Painting</option>
              </select>
            </div>

            <div style={styles.formGroup}>
              <label className="form-label">Service Issue *</label>
              <select name="serviceIssue" value={form.serviceIssue} onChange={handleChange} className="form-select">
                <option value="">Select an issue</option>
                <option value="leak">Water Leak</option>
                <option value="repair">Repair Needed</option>
                <option value="install">Installation</option>
                <option value="maintenance">Maintenance</option>
                <option value="inspection">Inspection</option>
              </select>
            </div>
          </div>
        </div>

        {/* Location Section */}
        <div style={styles.section}>
          <h3 className="section-title">📍 Location Details</h3>

          {/* Location Summary - Shows when location is selected */}
          {form.latitude && form.longitude && (
            <div style={styles.locationSummary}>
              <div style={styles.locationInfo}>
                <p style={styles.locationLabel}>Current Location</p>
                <p style={styles.locationNameDisplay}>{form.locationName || "Selected Location"}</p>
                <p style={styles.coordinatesSmall}>
                  {form.latitude}, {form.longitude}
                </p>
              </div>
              <button type="button" onClick={() => setShowMap(!showMap)} style={styles.changeLocationBtn}>
                {showMap ? "Hide Map" : "Show Map"}
              </button>
            </div>
          )}

          {/* Search Form */}
          <div style={styles.searchContainer}>
            <label className="form-label">Search or Click Map Below</label>
            <div className="search-form">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search location in Sri Lanka..."
                className="search-input"
              />
              <button type="button" onClick={handleSearchLocation} className="search-btn">
                🔍 Search
              </button>
            </div>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="search-results">
                {searchResults.map((result, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSelectSearchResult(result)}
                    className="search-result-item"
                  >
                    📍 {result.display_name.split(",")[0]}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Map Container - Full Width & Height */}
          {showMap && (
            <>
              <p className="map-helper-text">📍 Click anywhere on the map to pin your location</p>
              <div className="map-wrapper-container">
                <MapContainer
                  key={mapKey}
                  //show location icon
                  center={[parseFloat(form.latitude), parseFloat(form.longitude)] as [number, number]}
                  zoom={9}
                  style={{ height: "100%", width: "100%" }}
                >
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
                  <Marker position={[parseFloat(form.latitude), parseFloat(form.longitude)] as [number, number]}>
                    <Popup>📍 Your Selected Location</Popup>
                  </Marker>
                  <MapClickHandler onLocationSelect={handleLocationSelect} />
                </MapContainer>
              </div>
            </>
          )}
        </div>

        {/* Date & Time Section */}
        <div style={styles.section}>
          <h3 className="section-title">Schedule Details</h3>
          <div style={styles.gridThree}>
            <div style={styles.formGroup}>
              <label className="form-label">Service Date *</label>
              <input
                type="date"
                name="date"
                value={form.date}
                onChange={handleChange}
                className="form-input"
                //validation to prevent past dates
                min={new Date().toISOString().split("T")[0]}
              />
            </div>

            <div style={styles.formGroup}>
              <label className="form-label">Service Time *</label>
              <input type="time" name="time" value={form.time} onChange={handleChange} className="form-input" />
            </div>

            <div style={styles.formGroup}>
              <label className="form-label">Urgency Level *</label>
              <select name="urgency" value={form.urgency} onChange={handleChange} className="form-select">
                <option value="low">🟢 Low</option>
                <option value="normal">🟡 Normal</option>
                <option value="high">🔴 High</option>
              </select>
            </div>
          </div>
        </div>

        {/* Service Location Type */}
        <div style={styles.section}>
          <h3 className="section-title">Service Location Type</h3>
          <p style={styles.helperText}>Select one or both if applicable</p>
          <div className="checkbox-container">
            <div className="checkbox-wrapper">
              <input type="checkbox" name="indoor" checked={form.indoor} onChange={handleChange} />
              <label htmlFor="indoor">🏠 Indoor</label>
            </div>
            <div className="checkbox-wrapper">
              <input type="checkbox" name="outdoor" checked={form.outdoor} onChange={handleChange} />
              <label htmlFor="outdoor">🌳 Outdoor</label>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div style={styles.buttonSection}>
          {submitSuccess && (
            <div className="submit-success-banner">
               Your service request was submitted successfully!
            </div>
          )}
          {submitSuccess && weatherResult && (
            <div className="weather-result-card">
              <p className="weather-result-title">🌤 Weather Forecast for Your Service Date</p>
              <div className="weather-result-grid">
                <div className="weather-result-item">
                  <span className="weather-result-label">Condition</span>
                  <span className="weather-result-value">{weatherResult.condition}</span>
                </div>
                <div className="weather-result-item">
                  <span className="weather-result-label">Temperature</span>
                  <span className="weather-result-value">{weatherResult.temperature_c}°C</span>
                </div>
                <div className="weather-result-item">
                  <span className="weather-result-label">Rain Chance</span>
                  <span className="weather-result-value">{weatherResult.precipitation_probability_pct}%</span>
                </div>
                <div className="weather-result-item">
                  <span className="weather-result-label">Precipitation</span>
                  <span className="weather-result-value">{weatherResult.precipitation_mm} mm</span>
                </div>
                <div className="weather-result-item">
                  <span className="weather-result-label">Wind Speed</span>
                  <span className="weather-result-value">{weatherResult.wind_speed_kmh} km/h</span>
                </div>
              </div>
            </div>
          )}
          {submitError && (
            <div className="submit-error-banner">
              ❌ {submitError}
            </div>
          )}
          <button type="submit" disabled={!isFormValid || isSubmitting} className="submit-btn">
            {isSubmitting ? "Submitting..." : isFormValid ? "✓ Submit Request" : "Fill all required fields"}
          </button>
          <p className="required-note">* Required fields</p>
        </div>
      </form>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  form: {
    display: "grid",
    gap: "24px",
  },
  section: {
    display: "grid",
    gap: "16px",
    paddingBottom: "20px",
    borderBottom: "1px solid var(--border-default)",
  },
  gridTwo: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "16px",
  },
  gridThree: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "16px",
  },
  formGroup: {
    display: "grid",
    gap: "8px",
  },
  helperText: {
    fontSize: "clamp(11px, 2vw, 13px)",
    color: "var(--text-secondary)",
    margin: "0",
    fontWeight: "500",
  },
  searchContainer: {
    display: "grid",
    gap: "12px",
  },
  mapContainer: {
    display: "grid",
    gap: "12px",
  },
  mapContainerLarge: {
    display: "grid",
    gridTemplateRows: "min-content 1fr",
    gap: "8px",
    height: "500px",
    width: "100%",
    borderRadius: "12px",
    border: "2px solid var(--customer-500)",
    boxShadow: "0 8px 24px rgba(16, 185, 129, 0.2)",
    backgroundColor: "var(--bg-surface)",
  },
  mapHelper: {
    fontSize: "clamp(11px, 2vw, 12px)",
    color: "var(--text-secondary)",
    margin: "0",
    fontWeight: "500",
    padding: "12px 16px",
    backgroundColor: "var(--bg-input)",
    borderRadius: "6px",
  },
  locationSummary: {
    display: "grid",
    gridTemplateColumns: "1fr auto",
    gap: "16px",
    alignItems: "center",
    padding: "16px",
    backgroundColor: "var(--bg-surface)",
    border: "2px solid var(--customer-500)",
    borderRadius: "8px",
  },
  locationInfo: {
    display: "grid",
    gap: "4px",
  },
  locationLabel: {
    fontSize: "clamp(11px, 2vw, 12px)",
    color: "var(--text-secondary)",
    margin: "0",
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  locationNameDisplay: {
    fontSize: "clamp(14px, 3vw, 16px)",
    color: "var(--customer-400)",
    margin: "0",
    fontWeight: "700",
  },
  coordinatesSmall: {
    fontSize: "clamp(11px, 2vw, 12px)",
    color: "var(--text-primary)",
    margin: "0",
    fontFamily: "monospace",
    fontWeight: "600",
  },
  changeLocationBtn: {
    padding: "10px 16px",
    fontSize: "clamp(12px, 2vw, 13px)",
    fontWeight: "700",
    backgroundColor: "var(--bg-input)",
    color: "var(--customer-500)",
    border: "2px solid var(--customer-500)",
    borderRadius: "6px",
    cursor: "pointer",
    transition: "all 0.3s ease",
    whiteSpace: "nowrap",
  },
  coordinatesBox: {
    marginTop: "12px",
    padding: "14px",
    backgroundColor: "var(--bg-surface)",
    borderLeft: "4px solid var(--customer-500)",
    borderRadius: "8px",
    display: "grid",
    gap: "8px",
    border: "1px solid var(--border-default)",
  },
  locationNameText: {
    fontSize: "clamp(12px, 2.5vw, 14px)",
    color: "var(--customer-400)",
    margin: "0",
    fontWeight: "700",
  },
  buttonSection: {
    display: "grid",
    gap: "12px",
    paddingTop: "12px",
  },
};
