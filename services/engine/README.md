# Motor Python — P2/P3/P4

Un singur serviciu FastAPI, cu trei module. Browserul vorbește cu Next.js; Next.js transmite
cererea către Python cu un token intern. Fermierul nu are cont și motorul nu persistă cererea.

- P2: `fieldshift/data_service` — adaptor POWER și cache public.
- P3: `fieldshift/evaluator` — reguli, calendar, evaluare fără ponderile fermierului.
- P4: `fieldshift/recommender` — generare, comparație, ponderi și explicații.
- Integrare: `fieldshift/pipeline.py` și `fieldshift/api.py`.
- Demo fictiv: `fieldshift/demo.py`; nu utiliza funcția de calendar demo în motorul real.

`ENGINE_MODE=demo` întoarce exemple vizibil marcate. `computed` cere implementarea modulelor
P3/P4 și întoarce 503 până atunci. Nu este implementată o predicție a producției/profitului.
Adaptorul POWER există, dar nu a fost verificat live în această refacere.

Setup reproductibil de la rădăcină: `uv sync --project services/engine --frozen --extra dev`.
Versiunea de referință uv este 0.9.5; dependențele sunt fixate în `uv.lock`.
Schemele sunt în `packages/contracts/schemas`; exportă-le din workspace când schimbi contractul.

Vezi README rădăcină pentru comanda de pornire. Nu porni servicii într-o sarcină care cere
numai verificări statice. Testele unitare nu au nevoie de NASA, PostgreSQL sau server HTTP.
