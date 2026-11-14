# Frontend development

The interface lives in `apps/web`. It uses Next.js, React, TypeScript, and plain
CSS. Start with the existing shared contract; confirm input details with the
team before adding fields or changing request shapes.

## Where to work

| File | Responsibility |
| --- | --- |
| `apps/web/src/app/page.tsx` | Header, introduction, navigation, help, and footer |
| `apps/web/src/app/layout.tsx` | Document language, metadata, and global style imports |
| `apps/web/src/app/globals.css` | Colors, spacing, typography, responsive layouts, and focus styles |
| `apps/web/src/components/calculator.tsx` | Form state, existing inputs, location selection, and submission |
| `apps/web/src/components/recommendation-results.tsx` | Empty, loading, error, complete, limited, and insufficient-data states |
| `apps/web/src/components/plan-card.tsx` | One plan's three successive crops, dates, benefits, and trade-offs |
| `apps/web/src/components/ui/` | Reusable buttons, messages, and form section headings |
| `apps/web/src/lib/api.ts` | The frontend calculation adapter and explicit mock mode |

The interface and demonstration content use English. Values returned by future
data providers should also use English for display text. Do not translate IDs
or change shared contract keys to change presentation text.

## Preview the frontend locally

From the repository root, with Node.js and Corepack available:

```powershell
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @fieldshift/contracts generate
corepack pnpm --filter @fieldshift/web db:generate
```

If `apps/web/.env.local` does not exist, copy `apps/web/.env.example` to that
path. Preserve existing local settings. Set this value in `.env.local`:

```dotenv
NEXT_PUBLIC_USE_MOCK_API=true
```

Start only the web application:

```powershell
corepack pnpm --filter @fieldshift/web dev
```

Open the URL printed in the terminal, normally `http://localhost:3000`. Keep the
terminal open; saving source files updates the preview. Stop it with Ctrl+C.
Restart it after changing `.env.local`.

These direct workspace commands also work when `pnpm` is not on PATH and
`corepack enable` cannot write to `C:\Program Files\nodejs`.

Mock mode uses fictional results with a fixed calendar; form entries are not
evaluated. It does not require Python or PostgreSQL. The map and location search
use the internet. Never present demo output as real NASA observations or
calculated agronomic advice.

## Check changes

```powershell
corepack pnpm --recursive typecheck
git diff --check
```

For a manual browser review, check keyboard navigation and narrow and wide
screens. Confirm that demo notices remain visible and limited results show only
the plans actually returned. Static checks do not verify browser layout or
external services.
