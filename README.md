# Pet-Safe Flower Checker — Production-ready Frontend

This repository contains a polished React + Vite + Tailwind frontend for the Flower Safety API,
plus the backend `app.py` you uploaded copied into `/backend/app.py`.

**Backend URL (example):** https://flower-safety-api2.vercel.app/

## Features
- Modern responsive UI with Tailwind CSS
- Smooth animations using Framer Motion
- Autocomplete suggestions and polished result cards
- Environment-driven API URL (VITE_API_URL)
- Vercel-ready configuration (vercel.json)

## Deploying to Vercel
1. Push this repo to GitHub.
2. In Vercel, import the GitHub repository.
3. Set Environment Variable `VITE_API_URL` to your backend URL (e.g. `https://flower-safety-api2.vercel.app/`).
4. Build & output settings are automatic — Vercel will run `npm run build`. (If you need manual: Build Command=`npm run build`, Output Directory=`dist`)
5. Deploy.

## Running locally
```bash
npm install
# use .env.local to override API URL if needed:
# VITE_API_URL=https://flower-safety-api2.vercel.app/
npm run dev
```

## Notes
- The backend `app.py` is included under `/backend/app.py` for convenience — Vercel will not deploy Python from this repo unless configured.
- On Vercel, set VITE_API_URL in the Project Settings -> Environment Variables.

