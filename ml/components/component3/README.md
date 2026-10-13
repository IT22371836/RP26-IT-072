# Component 3 - Weekly Service Demand Forecasting

Component 3 predicts demand for 14 service categories for the next Monday-to-Sunday
window. The trained XGBoost model and its preprocessing artifacts are stored in
`artifacts/demand-v1` and are loaded by the backend Component 3 service.

The production sync command writes the generated payload to
`daily_demand/current` in Firebase Realtime Database. It uses the application's
existing Firebase Admin configuration; no credential or database URL is stored
with the model.

## Run a preview

From `packages/backend`:

```powershell
.venv\Scripts\python.exe scripts/sync_component3_demand.py
```

The command prints a summary and performs no database write by default. Add
`--write` to update `daily_demand/current`, after checking that the normal Firebase
environment settings are configured.

The version imported from the research implementation uses fixed baseline input
features for Colombo. These defaults are isolated in the service so operational
weather and booking aggregates can replace them without retraining the UI contract.
