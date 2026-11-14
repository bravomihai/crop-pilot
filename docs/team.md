# Împărțirea echipei

| Rol            | Fișiere principale                                                             | Livrabil                                                                      |
| -------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| P1 frontend    | `apps/web/src/components`, `src/app/page.tsx`, `globals.css`, `src/lib/api.ts` | Formular, localitate/punct, stare de așteptare și cele trei planuri           |
| P2 date        | `services/engine/fieldshift/data_service`                                      | Date zilnice, unități, calitate, surse, cache public                          |
| P3 agronomie   | `services/engine/fieldshift/evaluator`                                         | Reguli locale, calendar, verificări după istoricul real, evaluare pe criterii |
| P4 recomandări | `services/engine/fieldshift/recommender`, `pipeline.py`                        | Generarea și compararea a trei planuri cu câte trei culturi                   |
| P5 backend     | `apps/web/src/app/api`, `src/lib/server`, `prisma`, `compose.yaml`, `infra`    | Validare, integrare HTTP Python, cache Prisma/PostgreSQL, AWS                 |

## Lucru în paralel

P1 poate seta `NEXT_PUBLIC_USE_MOCK_API=true` și lucra pe exemplul comun. Nu implementează
formule agronomice în componente. P2/P3/P4 lucrează în module, cu aceleași date și funcții
de schimb, nu cu servere individuale. P5 păstrează serviciul Python în afara browserului.

P2: `build_environment(request) -> dict` cu date zilnice, surse și lipsuri.
P3: `load_rules(location) -> dict` și `evaluate(rotation,request,environment,rules) -> dict`.
P4: `recommend_rotations(request,environment,rules,evaluate) -> list[plan]`.
P3/P4 trebuie să convină un contract intermediar de evaluare înainte de implementare.
Contractul public request/result este deja comun și verificat în ambele limbaje.

Prima zonă acoperită este câmpia din sud și sud-est (Câmpia Română, Bărăgan, Dobrogea),
cu culturile de câmp principale. Fundulea rămâne doar punctul de test din exemple; în afara
zonei acoperite răspundem `insufficient_data`. Exemplul de localitate nu dovedește validare
agronomică.

Câmpurile opționale noi din contract (`current_rotation`/`baseline`, `plan.scores`,
`local_checks`, `history[].source`, `priorities.productivity`) sunt în `docs/api.md`.
Nimic nu se strică dacă nu le folosiți încă; adoptați-le când ajungeți la ele. Prioritățile/scenariile trebuie să influențeze evaluarea
reală numai după implementarea modelelor; demo declară explicit că nu le calculează.
