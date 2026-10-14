// Precarga global: se ejecuta en todas las páginas (ver BaseLayout).
//
// Al cargar la web (normalmente el inicio, que es liviano) aprovecha el
// tiempo muerto para descargar en segundo plano los datos pesados de las
// demás pestañas (`/map`, `/cars`, `/config`) y guardarlos en la caché de
// `api.js`. Así al cambiar de pestaña cada página pinta lo guardado al
// instante en vez de mostrar "Cargando…" y parpadear.
//
// También anticipa el HTML de las otras páginas (`<link rel="prefetch">`)
// y al pasar el puntero o el foco por el menú adelanta su descarga.
import { API, getJSON, peekCache } from "./api.js";

// Endpoints pesados por página (el inicio solo usa status/logs, livianos).
const PAGE_APIS = {
    "/map": [API.config, API.presets, API.tracks],
    "/cars": [API.config, API.entryList, API.availableCars],
    "/config": [API.config]
};

const PAGE_HREFS = Object.keys(PAGE_APIS);

function idle(callback) {
    if ("requestIdleCallback" in window) {
        window.requestIdleCallback(callback, { timeout: 4000 });
    } else {
        setTimeout(callback, 1500);
    }
}

function shouldSkip() {
    try {
        const conn = navigator.connection;
        // Con ahorro de datos o 2G no se precarga nada.
        if (conn && (conn.saveData || /2g/.test(conn.effectiveType || ""))) {
            return true;
        }
    } catch {
        // Sin Network Information API: se precarga igual.
    }
    return false;
}

async function prefetchUrl(url) {
    if (peekCache(url) !== null) {
        return;
    }
    try {
        await getJSON(url);
    } catch {
        // La página destino lo reintentará al abrirse; aquí no se molesta.
    }
}

async function prefetchAll() {
    const urls = [...new Set(Object.values(PAGE_APIS).flat())];
    // Secuencial y con pausa: evita saturar al backend recién arrancado.
    for (const url of urls) {
        await prefetchUrl(url);
    }
}

function prefetchPage(href) {
    if (document.querySelector(`link[rel="prefetch"][href="${href}"]`)) {
        return;
    }
    const link = document.createElement("link");
    link.rel = "prefetch";
    link.href = href;
    document.head.appendChild(link);
    for (const url of PAGE_APIS[href] || []) {
        prefetchUrl(url);
    }
}

if (!shouldSkip()) {
    idle(() => {
        // HTML de las demás pestañas + sus APIs.
        for (const href of PAGE_HREFS) {
            if (window.location.pathname !== href) {
                prefetchPage(href);
            }
        }
        prefetchAll();
    });

    // Al apuntar al menú se adelanta esa página concreta.
    for (const anchor of document.querySelectorAll("a.nav-item")) {
        const href = anchor.getAttribute("href");
        if (!PAGE_APIS[href]) {
            continue;
        }
        anchor.addEventListener("pointerenter", () => prefetchPage(href), {
            once: true
        });
        anchor.addEventListener("focus", () => prefetchPage(href), {
            once: true
        });
    }
}
