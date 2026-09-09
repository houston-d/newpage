# NewPage Webapp

Skeleton React frontend for NewPage, built with Vite.

## Prerequisites

- Node.js 18+

## Setup

```bash
npm install
```

## Run in development

```bash
npm run dev
```

## Build for production

```bash
npm run build
```

## Optional environment config

Copy `.env.example` to `.env` and adjust values:

- `VITE_API_BASE_URL`: backend base URL (defaults to `http://localhost:8000`)

## Project structure

- `src/main.jsx`: React entrypoint
- `src/App.jsx`: root app component
- `src/components/HealthStatus.jsx`: simple backend health status card
- `src/services/api.js`: tiny API helpers
- `src/styles/app.css`: app styles

