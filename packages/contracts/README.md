# Contracte comune

`src/index.ts` este sursa Zod/TypeScript. `pnpm contracts:generate` exportă scheme JSON
consumate de Python; schemele generate se comit. Exemplele JSON sunt fictive și permit
lucrul independent al frontendului. Nu copiați tipurile manual în web.

Cererea nu conține user_id, farm_id, email, telefon sau geometrie de parcelă. Rezultatul
conține până la trei planuri, fiecare cu trei culturi principale și ferestre calendaristice.
Exemplul este numai pentru dezvoltare. Vezi `docs/api.md` și `AGENTS.md`.

Orice schimbare de structură: sursă Zod + scheme regenerate + exemple + consumatori în
același PR. Semantica dintre câmpuri (ordine, surse, număr de planuri/status) este verificată
și de `validateResultSemantics`, pe lângă JSON Schema.
