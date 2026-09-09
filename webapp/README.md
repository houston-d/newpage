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
- `src/App.jsx`: app routes (including `/jobs` and `/jobs/{id}`)
- `src/services/api.js`: API helpers for backend requests
- `src/styles/app.css`: dark-green app styles
