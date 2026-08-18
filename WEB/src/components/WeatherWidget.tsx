import React, { useEffect, useState } from 'react';
import { 
  Sun, 
  Cloud, 
  CloudRain, 
  CloudLightning, 
  CloudFog, 
  Droplets, 
  Wind, 
  MapPin, 
  Loader2, 
  RefreshCw, 
  Compass, 
  CalendarDays, 
  AlertTriangle, 
  CheckCircle2, 
  Umbrella 
} from 'lucide-react';
import type { LocationCoords } from '../config/firebase';

export interface DailyForecastDay {
  date: string;
  maxTemp: number;
  minTemp: number;
  rain: number;
  weatherCode: number;
}

interface WeatherData {
  temperature: number;
  apparentTemperature: number;
  humidity: number;
  windSpeed: number;
  precipitation: number;
  cloudCover: number;
  isDay: number;
  weatherCode: number;
  daily: DailyForecastDay[];
}

interface WeatherWidgetProps {
  location?: LocationCoords;
  city?: string;
  district?: string;
  compact?: boolean;
  showDailyForecast?: boolean;
}

export const WeatherWidget: React.FC<WeatherWidgetProps> = ({
  location,
  city,
  district,
  compact: _compact = false,
  showDailyForecast = true
}) => {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  // Default to Colombo, Sri Lanka if no location provided
  const lat = location?.latitude || 6.9271;
  const lng = location?.longitude || 79.8612;

  const fetchWeather = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,cloud_cover,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code&timezone=auto&forecast_days=7`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch weather forecast data");
      const data = await res.json();
      const current = data.current;

      const dailyData: DailyForecastDay[] = [];
      if (data.daily && data.daily.time) {
        for (let i = 0; i < data.daily.time.length; i++) {
          dailyData.push({
            date: data.daily.time[i],
            maxTemp: Math.round(data.daily.temperature_2m_max[i] * 10) / 10,
            minTemp: Math.round(data.daily.temperature_2m_min[i] * 10) / 10,
            rain: Math.round((data.daily.precipitation_sum[i] || 0) * 10) / 10,
            weatherCode: data.daily.weather_code[i]
          });
        }
      }

      setWeather({
        temperature: Math.round(current.temperature_2m * 10) / 10,
        apparentTemperature: Math.round(current.apparent_temperature * 10) / 10,
        humidity: current.relative_humidity_2m,
        windSpeed: Math.round(current.wind_speed_10m * 10) / 10,
        precipitation: current.precipitation,
        cloudCover: current.cloud_cover,
        isDay: current.is_day,
        weatherCode: current.weather_code,
        daily: dailyData
      });
      setLastUpdated(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    } catch (err: any) {
      console.error("Open-Meteo weather fetch error:", err);
      setError("Unable to load weather forecast data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWeather();
  }, [lat, lng]);

  const getWeatherInfo = (code: number, isDay: number = 1) => {
    if (code === 0) return { label: isDay ? 'Clear Sky' : 'Clear Night', icon: <Sun size={24} color="#f59e0b" /> };
    if (code >= 1 && code <= 3) return { label: 'Partly Cloudy', icon: <Cloud size={24} color="#38bdf8" /> };
    if (code === 45 || code === 48) return { label: 'Foggy / Hazy', icon: <CloudFog size={24} color="#94a3b8" /> };
    if (code >= 51 && code <= 67) return { label: 'Rainy Showers', icon: <CloudRain size={24} color="#60a5fa" /> };
    if (code >= 80 && code <= 82) return { label: 'Heavy Rain', icon: <CloudRain size={24} color="#3b82f6" /> };
    if (code >= 95) return { label: 'Thunderstorm', icon: <CloudLightning size={24} color="#a855f7" /> };
    return { label: 'Cloudy', icon: <Cloud size={24} color="#cbd5e1" /> };
  };

  const formatDateLabel = (dateStr: string) => {
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const year = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10) - 1;
        const day = parseInt(parts[2], 10);
        const dateObj = new Date(year, month, day);

        const now = new Date();
        const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

        if (dateStr === todayStr) {
          return { dayName: 'Today', formattedDate: dateStr };
        }
        const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
        return { dayName, formattedDate: dateStr };
      }
    } catch {
      // fallback
    }
    return { dayName: dateStr, formattedDate: dateStr };
  };

  if (loading) {
    return (
      <div style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 67, 0.85) 100%)',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        borderLeft: '4px solid #38bdf8',
        borderRadius: '16px',
        padding: '24px',
        color: 'var(--text-muted)',
        minHeight: '200px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '10px'
      }}>
        <Loader2 size={24} className="spin" color="#38bdf8" />
        <span style={{ fontSize: '0.88rem', fontWeight: 500 }}>Connecting to Open-Meteo Weather API...</span>
      </div>
    );
  }

  if (error || !weather) {
    return (
      <div style={{
        background: 'rgba(15, 23, 42, 0.85)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
        borderLeft: '4px solid #ef4444',
        borderRadius: '16px',
        padding: '20px',
        color: '#fca5a5',
        fontSize: '0.86rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <strong>⚠️ Weather Error</strong>
          <button
            onClick={fetchWeather}
            style={{ background: 'none', border: 'none', color: '#38bdf8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
        <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.82rem' }}>{error}</p>
      </div>
    );
  }

  const { label, icon } = getWeatherInfo(weather.weatherCode, weather.isDay);
  const locationText = city && district ? `${city}, ${district}` : city || district || 'Sri Lanka';
  const heavyRainDays = weather.daily.filter(d => d.rain >= 15);

  return (
    <div className="glass-panel" style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--bg-card-border)',
      borderLeft: '5px solid var(--primary)',
      borderRadius: '18px',
      padding: '22px',
      boxShadow: 'var(--glass-shadow)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Background Decorative Accent */}
      <div style={{
        position: 'absolute',
        top: '-30px',
        right: '-30px',
        width: '120px',
        height: '120px',
        background: 'radial-gradient(circle, rgba(39, 98, 33, 0.08) 0%, transparent 70%)',
        pointerEvents: 'none'
      }} />

      {/* Header Info */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div>
          <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#276221', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Compass size={13} /> Live Weather & Appointment Planning
          </div>
          <h4 style={{ margin: '4px 0 0 0', fontSize: '1.1rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <MapPin size={16} color="#276221" /> {locationText}
          </h4>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)' }}>
            Updated: {lastUpdated || 'Just now'}
          </span>
          <button
            onClick={fetchWeather}
            title="Refresh Open-Meteo Weather"
            style={{
              background: '#f1f5f9',
              border: '1px solid #cbd5e1',
              borderRadius: '50%',
              width: '32px',
              height: '32px',
              color: '#276221',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease'
            }}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Main Content Row: Left Hero Temp + Right Detailed Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', alignItems: 'center' }}>
        
        {/* Left Primary Temperature Section */}
        <div style={{
          background: 'var(--input-bg)',
          border: '1px solid var(--input-border)',
          borderRadius: '14px',
          padding: '18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ background: 'var(--bg-card)', padding: '12px', borderRadius: '14px', border: '1px solid var(--bg-card-border)' }}>
              {icon}
            </div>
            <div>
              <div style={{ fontSize: '2.4rem', fontWeight: 800, color: '#0f172a', lineHeight: 1 }}>
                {weather.temperature}°C
              </div>
              <div style={{ fontSize: '0.88rem', color: '#276221', fontWeight: 600, marginTop: '4px' }}>
                {label}
              </div>
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', display: 'block' }}>Feels Like</span>
            <strong style={{ fontSize: '1.15rem', color: '#b45309' }}>{weather.apparentTemperature}°C</strong>
          </div>
        </div>

        {/* Right Detailed Environmental Metrics Stack */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '10px' }}>
          <div style={{ background: 'var(--input-bg)', padding: '12px', borderRadius: '12px', border: '1px solid var(--input-border)' }}>
            <span style={{ fontSize: '0.73rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>Relative Humidity</span>
            <strong style={{ fontSize: '0.96rem', color: '#0284c7', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Droplets size={14} /> {weather.humidity}%
            </strong>
          </div>

          <div style={{ background: 'var(--input-bg)', padding: '12px', borderRadius: '12px', border: '1px solid var(--input-border)' }}>
            <span style={{ fontSize: '0.73rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>Wind Speed</span>
            <strong style={{ fontSize: '0.96rem', color: '#7c3aed', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Wind size={14} /> {weather.windSpeed} km/h
            </strong>
          </div>

          <div style={{ background: 'var(--input-bg)', padding: '12px', borderRadius: '12px', border: '1px solid var(--input-border)' }}>
            <span style={{ fontSize: '0.73rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>Precipitation</span>
            <strong style={{ fontSize: '0.96rem', color: '#2563eb', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <CloudRain size={14} /> {weather.precipitation} mm
            </strong>
          </div>

          <div style={{ background: 'var(--input-bg)', padding: '12px', borderRadius: '12px', border: '1px solid var(--input-border)' }}>
            <span style={{ fontSize: '0.73rem', color: 'var(--text-muted)', display: 'block', marginBottom: '2px' }}>Cloudiness</span>
            <strong style={{ fontSize: '0.96rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Cloud size={14} /> {weather.cloudCover}%
            </strong>
          </div>
        </div>
      </div>

      {/* Appointment Scheduling Weather Advisory Banner */}
      {showDailyForecast && weather.daily && weather.daily.length > 0 && (
        <div style={{
          marginTop: '20px',
          background: heavyRainDays.length > 0
            ? 'rgba(239, 68, 68, 0.1)'
            : '#eaf3e8',
          border: heavyRainDays.length > 0
            ? '1px solid #ef4444'
            : '1px solid #276221',
          borderRadius: '12px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          {heavyRainDays.length > 0 ? (
            <AlertTriangle size={20} color="#dc2626" style={{ flexShrink: 0 }} />
          ) : (
            <CheckCircle2 size={20} color="#276221" style={{ flexShrink: 0 }} />
          )}
          <div style={{ fontSize: '0.84rem', color: heavyRainDays.length > 0 ? '#b91c1c' : '#1d4b19', lineHeight: 1.4 }}>
            <strong>Appointment Advisory: </strong>
            {heavyRainDays.length > 0 ? (
              <span>
                Heavy rainfall expected on <span style={{ color: '#dc2626', fontWeight: 600 }}>{heavyRainDays.map(d => d.date).join(', ')}</span>.
                Consider adjusting outdoor appointments or preparing rain precautions.
              </span>
            ) : (
              <span>
                Weather conditions look favorable for field appointments and client meetings over the coming 7 days.
              </span>
            )}
          </div>
        </div>
      )}

      {/* Daily Forecast Section */}
      {showDailyForecast && weather.daily && weather.daily.length > 0 && (
        <div style={{ marginTop: '22px', borderTop: '1px solid #e2e8f0', paddingTop: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h5 style={{ margin: 0, fontSize: '0.94rem', color: '#0f172a', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CalendarDays size={18} color="#276221" /> 7-Day Weather Forecast
            </h5>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              Open-Meteo Daily API
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(125px, 1fr))',
            gap: '10px'
          }}>
            {weather.daily.map((day) => {
              const dayInfo = getWeatherInfo(day.weatherCode, 1);
              const { dayName, formattedDate } = formatDateLabel(day.date);
              const isHeavyRain = day.rain >= 15;

              return (
                <div key={day.date} style={{
                  background: isHeavyRain ? 'rgba(239, 68, 68, 0.08)' : 'var(--input-bg)',
                  border: isHeavyRain ? '1px solid #ef4444' : '1px solid var(--bg-card-border)',
                  borderRadius: '12px',
                  padding: '12px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  transition: 'transform 0.15s ease, border-color 0.15s ease'
                }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#0f172a' }}>
                    {dayName}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    {formattedDate}
                  </span>

                  <div style={{ marginBottom: '6px' }}>
                    {dayInfo.icon}
                  </div>

                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '8px', minHeight: '32px', display: 'flex', alignItems: 'center' }}>
                    {dayInfo.label}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', marginBottom: '6px' }}>
                    <span style={{ color: '#dc2626', fontWeight: 700 }}>{day.maxTemp}°C</span>
                    <span style={{ color: 'var(--text-muted)' }}>/</span>
                    <span style={{ color: '#0284c7', fontWeight: 600 }}>{day.minTemp}°C</span>
                  </div>

                  <div style={{
                    fontSize: '0.74rem',
                    padding: '3px 8px',
                    borderRadius: '20px',
                    background: isHeavyRain ? 'rgba(239, 68, 68, 0.15)' : day.rain > 0 ? 'rgba(2, 132, 199, 0.12)' : '#f1f5f9',
                    color: isHeavyRain ? '#dc2626' : day.rain > 0 ? '#0284c7' : 'var(--text-muted)',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <Umbrella size={12} /> {day.rain} mm
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer GPS Coordinates */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #e2e8f0', fontSize: '0.74rem', color: 'var(--text-dim)' }}>
        <span>📍 GPS Coordinates: Latitude {lat.toFixed(4)}, Longitude {lng.toFixed(4)}</span>
        <span>Data Provided by Open-Meteo API</span>
      </div>
    </div>
  );
};
