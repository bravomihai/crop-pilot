# [CropPilot](https://crop-pilot.nemes.engineer/)

CropPilot helps farmers in Romania compare crop rotations based on field location, crop history, soil conditions, irrigation, and planning priorities. It generates up to three alternative plans, each with three successive main crops, sowing and harvest windows, and clear benefits and trade-offs.

Plans are evaluated against historical weather and regional crop rules for water demand, soil impact, climate risk, and productivity potential. Farmers can compare their current rotation, explore temperature and rainfall scenarios, and test plans against difficult historical seasons.

CropPilot supports agricultural decisions; its rules and scores require local agronomic review. Scenarios are not forecasts, and financial figures are rough estimates.

## Stack

- **Next.js, React, and TypeScript** — web interface and API, with Leaflet for interactive maps.
- **Python and FastAPI** — environmental data processing, rule-based evaluation, and crop rotation recommendations.
- **PostgreSQL and Prisma** — optional caching of public environmental data; **Zod** and JSON Schema define shared API contracts.
- **Docker Compose** — local services and deployment packaging. An optional **OpenAI** integration explains computed results in plain English.

## NASA data integrations

- **[NASA POWER](https://power.larc.nasa.gov/)** — historical daily temperature, precipitation, humidity, wind, and solar radiation. These support crop evaluation, drought and heat indicators, and reference evapotranspiration calculations.
- **[SRTM elevation](https://www.opentopodata.org/datasets/srtm/)** — terrain data accessed through OpenTopoData to estimate slope for erosion-risk assessment.

Additional sources include ISRIC SoilGrids for soil estimates and ESA WorldCover for historical land-cover screening. Environmental datasets provide regional or modelled context rather than field measurements.
