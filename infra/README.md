# AWS — calculator web fără conturi

Pentru început: web Next.js și engine Python în containere pe EC2 sau ECS/Fargate.
PostgreSQL poate rula local în Compose; pe AWS folosiți RDS PostgreSQL dacă doriți cache
persistent administrat. Cache-ul este opțional și se poate dezactiva.

- Publicați numai web-ul prin HTTPS, cu reverse proxy/load balancer.
- Engine comunică prin rețeaua privată, folosind `INTERNAL_API_TOKEN`.
- Nu expuneți PostgreSQL sau endpointul engine către internet.
- Configurați secretul din SSM/Secrets Manager; valorile din exemple sunt numai locale.
- Rulați `pnpm db:deploy` ca pas de release, cu DATABASE_URL corespunzător, înainte de cache.
- Folosiți HTTPS către RDS cu certificatul CA adecvat; nu dezactivați verificarea TLS.
- Next.js așteaptă motorul până la `ENGINE_TIMEOUT_MS` (implicit 90 secunde); configurați
  timeoutul proxy-ului peste această limită. Pentru calcule mai lungi, proiectați explicit
  o coadă și retenția datelor; nu introduceți implicit persistența cererilor fermierilor.
- Limitați cererile la nivelul proxy/AWS WAF și verificați traficul fără a loga formulare.
- Nu trimiteți SMS și nu reconfigurați numărul/webhookul Anveo existent pentru acest repo.

Nu există infrastructură creată sau deploy efectuat de această refacere.
Exemplu de proxy: `Caddyfile.example` (adaptați domeniul și rețeaua).

Surse: Next.js https://nextjs.org/docs/app/getting-started/deploying
ECS https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html
RDS https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html

Geocoding: https://open-meteo.com/en/docs/geocoding-api (noncommercial prototype; review terms before commercial use).
Map tiles: https://operations.osmfoundation.org/policies/tiles/ (attribution, normal browser caching, no bulk download).

CI: `ci/checks.yml.example` conține verificările propuse. Nu este activ pe GitHub; pentru
activare mutați-l în `.github/workflows/checks.yml` cu acces workflow corespunzător.
