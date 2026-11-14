# Build from the repo root so the contracts (used in mock mode) are included:
#   docker build -f backend/Dockerfile -t fieldshift-backend .
FROM node:22-alpine AS build
WORKDIR /app/backend
COPY backend/package*.json ./
RUN npm ci
COPY backend ./
RUN npm run build

FROM node:22-alpine
WORKDIR /app/backend
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 CONTRACTS_DIR=/app/contracts
COPY contracts /app/contracts
COPY --from=build /app/backend/.next/standalone ./
COPY --from=build /app/backend/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
