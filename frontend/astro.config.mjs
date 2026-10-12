import { defineConfig } from "astro/config";

// Backend FastAPI al que el servidor de desarrollo reenvía /api.
// Se puede cambiar con la variable de entorno ASTRO_API_TARGET.
const API_TARGET =
    process.env.ASTRO_API_TARGET || "http://localhost:9094";

// En desarrollo, Astro (4321) reenvía /api al backend FastAPI (9094).
// En producción, Astro genera HTML estático en ./dist y FastAPI sirve
// tanto las páginas como la API desde el mismo origen (sin CORS).
export default defineConfig({
    outDir: "./dist",
    build: {
        format: "directory"
    },
    vite: {
        build: {
            // El backend sirve una CSP con `script-src 'self'` (sin
            // 'unsafe-inline'): nada de scripts incrustados en el HTML. Por
            // eso los scripts deben salir siempre como archivo aparte.
            assetsInlineLimit: 0
        },
        server: {
            proxy: {
                "/api": {
                    target: API_TARGET,
                    changeOrigin: true
                }
            }
        }
    }
});
