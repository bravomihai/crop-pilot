# Infrastructură FieldShift

- `compose.yaml`: PostgreSQL local, migrare, web, motor, gateway NGINX și mentenanță cache.
- `nginx.conf`: limite de cereri și corpuri, blocarea API-ului intern la accesul public.
- `cache-maintenance.py`: curățare periodică autentificată a datelor publice expirate.
- `Caddyfile` + `compose.production.yaml`: profil HTTPS, fără porturi directe pentru servicii.
- `aws/host.yaml`, `aws/configure.py`, `aws/README.md`: infrastructură EC2 pregătită și
  încărcarea secretelor; nicio resursă AWS nu a fost creată.
- `.github/workflows/checks.yml`: verificări pregătite pentru rulare la push/PR.
  `ci/checks.yml.example` este copia de referință; workflow-ul nu a rulat pe GitHub încă.

## Verificare locală

Cu Node disponibil în shell și dependențele instalate, pornește configurația locală:

```sh
docker compose up -d --build --wait
pnpm test:cache
services/engine/.venv/bin/python infra/check-local.py
```

Scriptul de integrare folosește numai localhost. Verifică motorul demo, geocodarea live,
cache-ul și limitele gateway-ului; oprește temporar numai PostgreSQL al acestui proiect
și recreează temporar engine în `computed`, apoi restaurează baza și `demo`. Nu îl rula
pe un deployment comun. Nu șterge volume sau date active. Migrarea se face automat ca
serviciu separat în Compose. Configurația locală este ignorată de Git.

Aplicația cu limite publice: `http://localhost:8080`; portul direct de dezvoltare este
3000. Baza și motorul sunt publicate numai pe loopback în profilul local. Pentru producție,
folosește profilul din [ghidul AWS](aws/README.md), care elimină aceste porturi.

Cache-ul stochează numai date publice. Formularele, istoricul introdus și recomandările
fermierilor nu sunt persistate. Nu se trimit mesaje SMS/WhatsApp.

Surse primare pentru configurație: [NGINX](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html),
[Compose](https://docs.docker.com/reference/compose-file/merge/),
[node-postgres](https://node-postgres.com/apis/client),
[Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
