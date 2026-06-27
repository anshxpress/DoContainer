# DOCSCOPE AI — Frontend (Next.js)

> For full project setup instructions including Docker, backend, and database, see the [root README](../README.md).

---

## Frontend Quick Start

```powershell
# From d:\docscope\frontend
npm install      # first time only
npm run dev      # start dev server
```

Open **[http://localhost:3000](http://localhost:3000)** in your browser.

> **Requires the backend to be running** on `http://localhost:8001`. See [root README → Start the Backend](../README.md#2-start-the-backend).

---

## Frontend Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 16.2.9 | React framework (App Router) |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 4.x | Utility-first styling |
| Turbopack | bundled | Fast dev bundler |
| lucide-react | 1.21 | Icons |

## Available Scripts

```powershell
npm run dev      # Start development server (http://localhost:3000)
npm run build    # Build production bundle
npm run start    # Serve production build
npm run lint     # Run ESLint
```

## Project Structure

```
frontend/src/
├── app/                 # Next.js App Router pages
│   ├── (dashboard)/     # Dashboard layout group
│   │   └── dashboard/   # Main dashboard page
│   └── layout.tsx       # Root layout
└── components/          # Shared UI components
```
