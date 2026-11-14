# Motor Python — P2/P3/P4

Un singur serviciu FastAPI, cu trei module. Browserul vorbește cu Next.js; Next.js transmite
cererea către Python cu un token intern. Fermierul nu are cont și motorul nu persistă cererea.

- P2: `fieldshift/data_service` — adaptor POWER și cache public.
- P3: `fieldshift/evaluator` — reguli, calendar, evaluare fără ponderile fermierului.
- P4: `fieldshift/recommender` — generare, comparație, ponderi și explicații.
- Integrare: `fieldshift/pipeline.py` și `fieldshift/api.py`.
- Demo fictiv: `fieldshift/demo.py`; nu utiliza funcția de calendar demo în motorul real.

`ENGINE_MODE=demo` întoarce exemple vizibil marcate. `computed` rulează NASA POWER, ET₀ FAO-56, SoilGrids opțional și evaluatorul/recommenderul
transparent; cere `ENABLE_NASA_POWER=true`. Datele externe nu au fost verificate live în
această refacere. Răspunsul calculat include, pentru fiecare lună observată, media și extrema
zilnică a temperaturilor maxime/minime, cu numărul de observații valide. Aceste date ajută
la interpretarea riscului termic; nu sunt prognoze și nu oferă încă numărători lunare de zile
de căldură pentru fiecare plan. `sources` (cu titlu) și `data_gaps` sunt câmpuri de nivel
superior.

Coordonatele sunt verificate față de limita României geoBoundaries ADM0 (CC BY 3.0).
Cererea poate conține un contur Polygon desenat și o listă opțională de culturi selectate.
Până la agregarea zonală, NASA POWER și SoilGrids folosesc `location`, nu întregul contur;
limita aceasta este semnalată în `data_gaps`.
Regulile locale documentate acoperă sudul/sud-estul României. În alte zone românești se
folosește temporar catalogul acestei regiuni, cu date de semănat/recoltat ajustate după
temperatura medie NASA POWER aprilie–septembrie. Aceste benzi nu sunt o zonare agroclimatică
oficială, iar calendarul nu este validat local. Coeficienții FAO-56 sunt valori generale.
Scorurile compară adecvarea istorică precipitații/ETc, o percentilă 20 a rezultatelor
pe sezoane și un proxy de structură a rotației. SoilGrids nu influențează scorul; lipsesc
praguri locale validate. Modelul nu estimează producția/profitul și nu modelează precipitația
efectivă, scurgerea, drenajul sau stocarea apei în sol. Nu folosiți rezultatul ca recomandare
agronomică validată.

Setup reproductibil de la rădăcină: `uv sync --project services/engine --frozen --extra dev`.
Versiunea de referință uv este 0.9.5; dependențele sunt fixate în `uv.lock`.
Schemele sunt în `packages/contracts/schemas`; exportă-le din workspace când schimbi contractul.

Vezi README rădăcină pentru comanda de pornire. Nu porni servicii într-o sarcină care cere
numai verificări statice. Testele unitare nu au nevoie de NASA, PostgreSQL sau server HTTP.
