# Usar la imagen oficial de Node.js como imagen base
FROM node:lts-alpine as build-stage

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar package.json y pnpm-lock.yaml al directorio de trabajo
COPY package.json pnpm-lock.yaml ./

# Habilitar corepack e instalar una versión compatible de pnpm (lockfileVersion 6.0 requiere pnpm 8.x)
RUN corepack enable && corepack prepare pnpm@8 --activate
# Instalar las dependencias del proyecto
RUN pnpm install

# Copiar los archivos del proyecto al directorio de trabajo
COPY . .

# Construir el proyecto y limpiar la caché
RUN pnpm build && \
    pnpm store prune && \
    rm -rf node_modules

# Usar la imagen de Nginx como imagen base
FROM nginx:stable-alpine as production-stage

# Copiar el resultado de la compilación al directorio de servicio de Nginx
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copiar la configuración de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Añadir healthcheck (comprobar si existe index.html)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD test -f /usr/share/nginx/html/index.html || exit 1

# Exponer el puerto 80
EXPOSE 80

# Iniciar el servidor Nginx
CMD ["nginx", "-g", "daemon off;"]
