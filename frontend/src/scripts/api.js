// Cliente HTTP mínimo para la API de FastAPI.
// Las URLs son relativas: funcionan tanto en desarrollo
// (proxy de Astro a FastAPI) como en producción (mismo origen).
export const API = {
    status: "/api/server/status",
    logs: "/api/server/logs",
    config: "/api/server/config",
    presets: "/api/server/weather-presets",
    entryList: "/api/server/entry-list",
    tracks: "/api/server/tracks",
    availableCars: "/api/server/available-cars",
    start: "/api/server/start",
    stop: "/api/server/stop",
    restart: "/api/server/restart"
};

// ---------- Caché en sessionStorage (stale-while-revalidate) ----------
// Al cargar cualquier página se precargan los endpoints pesados y se
// guardan aquí. Al entrar a otra pestaña se pinta lo guardado al instante
// (sin "Cargando…") y luego se revalida en segundo plano. Vive solo en la
// pestaña actual: no hay datos personales persistentes entre sesiones.
const CACHE_PREFIX = "asseto:api:";
const CACHE_TTL = 90_000; // 90 s: suficiente para navegar entre pestañas

function cacheKey(url) {
    return `${CACHE_PREFIX}${url}`;
}

export function peekCache(url) {
    try {
        const raw = sessionStorage.getItem(cacheKey(url));
        if (!raw) {
            return null;
        }
        const { time, data } = JSON.parse(raw);
        if (!time || Date.now() - time > CACHE_TTL) {
            sessionStorage.removeItem(cacheKey(url));
            return null;
        }
        return data;
    } catch {
        return null;
    }
}

export function writeCache(url, data) {
    try {
        sessionStorage.setItem(
            cacheKey(url),
            JSON.stringify({ time: Date.now(), data })
        );
    } catch {
        // Almacenamiento lleno o bloqueado: se sigue sin caché.
    }
}

async function request(url, options) {
    let response;

    try {
        response = await fetch(url, options);
    } catch {
        // Fallo de red: mensaje comprensible en lugar de "Failed to fetch".
        throw new Error("No se pudo conectar con el backend");
    }

    if (!response.ok) {
        // El backend devuelve { detail } con la causa (p. ej. systemctl).
        let detail = `Error ${response.status}`;
        try {
            const body = await response.json();
            if (body && body.detail) {
                detail = body.detail;
            }
        } catch {
            // Respuesta sin JSON: nos quedamos con el código.
        }
        const error = new Error(detail);
        // El código se conserva para distinguir "el origen no permitido" (403,
        // otra web intentó disparar la acción) de "el servidor no arrancó" (502).
        error.status = response.status;
        throw error;
    }

    return response.json();
}

export function getJSON(url) {
    // Sin cabeceras, sin tokens y sin credenciales: este panel no tiene
    // usuarios ni contraseñas. Los POST se frenan por `Origin` (CSRF).
    // `fetch` ya envía `credentials: "same-origin"` por defecto.
    // Los GET exitosos se guardan en caché para pintar al instante al
    // cambiar de pestaña (ver peekCache/writeCache).
    return request(url).then(data => {
        writeCache(url, data);
        return data;
    });
}

export function postJSON(url, body) {
    return request(url, {
        method: "POST",
        headers: body
            ? { "Content-Type": "application/json" }
            : undefined,
        body: body ? JSON.stringify(body) : undefined
    });
}

export function putJSON(url, body) {
    return request(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    }).then(data => {
        // Tras guardar, lo respondido ya es lo fresco: actualiza la caché
        // para no repintar lo viejo al volver a la pestaña.
        writeCache(url, data);
        return data;
    });
}
