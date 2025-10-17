FROM node:20-alpine
WORKDIR /app

# Copy manifests first to leverage Docker layer caching
COPY package.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/ui/package.json packages/ui/package.json

# Install workspace deps at repo root so workspaces link properly
RUN npm install

# Copy sources (entire repo)
COPY . .

# Build the web workspace
RUN npm run build --workspace apps/web

EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "apps/web"]
