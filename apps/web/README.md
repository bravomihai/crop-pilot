# Web — P1/P5

Next.js App Router conține atât React cât și endpointurile backend. Nu există frontend
Vite separat, CORS între două aplicații, conturi, sesiuni persistente sau stocare de ferme.

P1 lucrează în `src/components`, `src/app/page.tsx`, `src/app/globals.css` și `src/lib/api.ts`.
P5 lucrează în `src/app/api`, `src/lib/server`, `prisma` și configurarea deploymentului.

`NEXT_PUBLIC_USE_MOCK_API=true` permite dezvoltarea interfeței fără Python. Datele sunt
fictive și marcate. În modul normal, `POST /api/recommendations` transmite formularul
validat către engine și returnează rezultatul, fără a-l salva.

Prisma CLI citește `.env` prin `prisma.config.ts`. Next.js citește `.env.local`.
Schema/migrația păstrează doar cache public. `CACHE_ENABLED=false` dezactivează cache-ul.
Comenzile pnpm se execută de la rădăcină; vezi README și AGENTS.md.
