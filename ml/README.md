# Machine Learning Workspace

Each research component has the same layout:

- `data/raw`: immutable source datasets
- `data/processed`: reproducible preprocessing outputs
- `notebooks`: Colab or Jupyter experimentation and training
- `src`: reusable Python preprocessing, training, and evaluation code
- `artifacts`: exported files required for inference
- `reports`: metrics, plots, and evaluation outputs

Training notebooks should call reusable code from `src` as the project matures. A deployable artifact must include an `artifact-manifest.json` describing its model version, source dataset version, metrics, framework versions, and files.
