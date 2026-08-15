# PatientCapital web

Vinext/React client for the local PatientCapital API. The browser renders API
results; allocation and portfolio arithmetic stay in the Python domain layer.

## Commands

```bash
npm ci
npm run api:types   # requires API on http://127.0.0.1:8000
npm run dev
npm test
```

Set `NEXT_PUBLIC_API_BASE_URL` only when the API is not available at the local
default. `app/api-types.ts` is generated from FastAPI OpenAPI and must not be
edited manually.
