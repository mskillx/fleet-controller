FROM node:20-alpine AS builder

ARG VITE_THEME=blue
ARG VITE_API_URL=http://localhost:8000
ENV VITE_THEME=$VITE_THEME
ENV VITE_API_URL=$VITE_API_URL

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
