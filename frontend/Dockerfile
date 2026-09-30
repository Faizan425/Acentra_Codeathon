FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# Vite dev server keeps the demo interactive (hot reload) and needs no build step.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
