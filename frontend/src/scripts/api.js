// Cliente HTTP mínimo para la API de FastAPI.
// Las URLs son relativas: funcionan tanto en desarrollo
// (proxy de Astro a FastAPI) como en producción (mismo origen).
export const API = {
    status: "/api/server/status",
    logs: "/api/server/logs",
    start: "/api/server/start",
    stop: "/api/server/stop",
    restart: "/api/server/restart"
};

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
    return request(url);
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
