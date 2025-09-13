FROM node:20

WORKDIR /app
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./
RUN if [ -f package-lock.json ]; then npm ci;     elif [ -f yarn.lock ]; then yarn;     elif [ -f pnpm-lock.yaml ]; then corepack enable && pnpm i;     else npm i; fi
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
