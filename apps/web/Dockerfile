FROM node:22-bookworm-slim AS development
WORKDIR /workspace
ENV NEXT_TELEMETRY_DISABLED=1
COPY package*.json ./
COPY apps/web/package*.json ./apps/web/
RUN npm install
COPY apps/web ./apps/web
EXPOSE 3000
CMD ["npm", "run", "dev:web"]
