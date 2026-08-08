# weda.lk Web Application (`WEB`)

## Gradual FastAPI integration

Copy `.env.example` to `.env` and select the transition mode:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_DATA_SOURCE=firebase
VITE_AUTH_SOURCE=firebase
VITE_FILE_STORAGE_SOURCE=firebase
```

- `firebase` keeps the original WEB behavior and is the rollback-safe default.
- `hybrid` keeps Firebase authoritative and explicitly mirrors customer profile updates to
  FastAPI. Use it with `VITE_AUTH_SOURCE=firebase-link` after the same user account exists in
  both authentication systems.
- `fastapi` is reserved for feature-by-feature cutover. FastAPI-only login remains disabled
  until the customer, provider, and administrator dashboards all have complete backend
  contracts.

The adapters preserve the existing Firebase-shaped customer and provider objects and map
only at `src/services/customer-service.ts` and `src/services/provider-service.ts`. Backend
failures in hybrid/FastAPI mode are surfaced; they are not silently replaced with
browser-local data. Provider file bytes remain in Firebase Storage, while protected FastAPI
endpoints store private metadata, use soft deletion, and lock document changes after a
verification request.

This directory contains the React 19 + TypeScript + Vite web application for the **weda.lk** Service Provider Rating, Demand Forecasting & Recommendation System (SLIIT 2026).

> 📌 **Master Project Documentation**: For complete system architecture, ML model evaluation, database schemas, and OCR credibility pipeline details, please refer to the [Root README.md](../README.md).

---

## 🛠️ Tech Stack

* **Core**: React 19, TypeScript 5, Vite 8
* **Styling**: Vanilla CSS Design Tokens, Glassmorphism UI
* **Maps & Geolocation**: Leaflet, React-Leaflet, OpenStreetMap
* **Backend Integration**: Firebase Realtime Database (RTDB), Firebase Auth, Firebase Storage
* **Icons**: Lucide React
* **Linter**: Oxlint

---

## 💻 Available Scripts

In this directory, you can run:

### `npm run dev`
Runs the app in development mode with Hot Module Replacement (HMR).
Open [http://localhost:5173](http://localhost:5173) to view it in your browser.

### `npm run build`
Builds the app for production to the `dist` folder.
It correctly bundles React in production mode and optimizes the build for performance.

### `npm run preview`
Locally preview the production build.

### `npm run lint`
Runs `oxlint` to check for syntax and React quality rules.

---

## 📁 Component Directory

* `src/components/CustomerDashboard.tsx` — Main interface for customers to search providers, pick location coordinates on a Leaflet map, submit service requests, and rate providers.
* `src/components/ProviderDashboard.tsx` — Management dashboard for service providers to configure profiles, set working hours, upload verification documents, and view credibility score badges.
* `src/components/Dashboard.tsx` — Administrative portal for system-wide metrics and user account management.
* `src/components/WeeklyDemandTimetable.tsx` — Interactive heatmap timetable displaying predicted demand levels across 14 service categories for the week.
* `src/components/WeatherWidget.tsx` — Live Open-Meteo weather integration for local environmental conditions and travel advisories.
* `src/components/WorkingHoursEditor.tsx` — Interactive schedule configuration tool for providers.
* `src/config/firebase.ts` — Firebase configuration, authentication helper routines, RTDB real-time sync, and fallback data models.
