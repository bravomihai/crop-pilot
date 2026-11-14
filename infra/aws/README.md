# AWS — configurație pregătită, fără publicare automată

Varianta de prototip folosește un singur EC2: Caddy pentru HTTPS, NGINX pentru limite,
Next.js, Python și PostgreSQL pentru cache. Nu este o configurație cu disponibilitate
ridicată. Cache-ul poate fi reconstruit. Nu conține date de fermieri.

`host.yaml` creează gazda Amazon Linux 2023 într-un VPC/subnet public existente, un rol
pentru administrare SSM și citirea a două secrete, un disc criptat și intrări numai pe
80/443. Nu creează domeniu, certificat, parametri SSM, RDS sau aplicație. Crearea resurselor
AWS implică costuri; nu a fost executată în această sarcină.

## Pregătirea pentru o publicare viitoare

La momentul publicării trebuie alese regiunea, VPC-ul, subnetul public și domeniul.
Creează parametri SSM de tip SecureString, cu cheia AWS implicită pentru SSM:
`/fieldshift/production/internal-token` (cel puțin 32 caractere URL-safe aleatoare) și
`/fieldshift/production/database-password` (cel puțin 24). Nu reutiliza valorile locale.
Dacă alegi o cheie KMS proprie, adaugă permisiunea de decriptare strict pentru acea cheie.

Validează și aplică `host.yaml` prin CloudFormation cu `CAPABILITY_IAM`, după revizuirea
parametrilor și costurilor. Administrarea este prin SSM, nu SSH. Hostul instalează Docker
și Compose 2.39.4, verificând suma SHA-256 publicată. Așteaptă finalizarea bootstrapului
înainte să rulezi Docker. Copiază o versiune revizuită a surselor în `/opt/fieldshift`,
fără `.env*`, dependențe sau artefacte locale. Pentru repo privat folosește un acces Git
separat; nu include credențiale în UserData. Nu este automatizat transferul surselor.

Din rădăcina surselor de pe host, cu permisiuni de scriere și acces Docker, configurează:

```sh
python3 infra/aws/configure.py --region <regiune> --domain <domeniu> --email <email>
```

Scriptul citește secretele folosind rolul hostului și creează `.env.production`, cu
permisiuni 0600. Refuză suprascrierea unui fișier existent. Nu afișează secretele. Ambele
servicii primesc același token din această configurație. Nu rula `docker compose config`
fără `--quiet`, deoarece poate afișa valori de mediu.

După ce DNS-ul A al domeniului indică IP-ul gazdei și porturile 80/443 sunt accesibile:

```sh
docker compose -p fieldshift-production --env-file .env.production -f compose.yaml -f infra/compose.production.yaml config --quiet
docker compose -p fieldshift-production --env-file .env.production -f compose.yaml -f infra/compose.production.yaml up -d --build --wait
```

Caddy obține și reînnoiește certificatul. În acest profil nu sunt publicate porturi
pentru web, engine, gateway sau PostgreSQL. Rutele `/api/internal/*` sunt blocate de
NGINX, iar Python le accesează direct prin rețeaua Compose. Limitele se aplică per IP:
5 calcule/minut, 60 căutări/minut, 30 verificări engine/minut, cu burst-uri documentate
în `infra/nginx.conf`. Nu publica separat gateway-ul și nu adăuga CDN/proxy în fața
Caddy fără să configurezi explicit sursele de IP de încredere.

Verifică `/api/health`, `/api/engine/status` și o cerere demo. `computed` rămâne o
integrare ulterioară, când P2/P3/P4 sunt gata și verificate. Schimbarea modului în sine
nu validează modelele. IP-ul public se poate schimba la stop/start; actualizează DNS
sau alocă separat un Elastic IP dacă este necesar.

## Limite de operare

Logurile aplicației au ID, operație, status, cod de eroare și durată. Nu au formulare,
coordonate, query-uri sau tokenuri. Logurile HTTP de acces ale proxy-ului sunt dezactivate.
Logurile Docker au rotație. Curățarea cache-ului rulează la pornirea serviciului de
mentenanță și apoi la fiecare oră, în loturi limitate. Nu este stocare persistentă de
analize. Pierderea hostului poate pierde cache-ul; nu se promite recuperare sau HA.

CloudFormation și sintaxa locală pot fi validate fără crearea unei resurse. Configurația
AWS și obținerea certificatului trebuie verificate separat la deployment.

Surse primare: [EC2 CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-instance.html),
[SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html),
[Compose merge](https://docs.docker.com/reference/compose-file/merge/),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[NGINX limit_req](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).
