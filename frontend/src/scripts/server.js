// Control del servidor de Assetto Corsa.
//
// No hay login, ni usuarios, ni contraseñas: el panel carga y los botones
// funcionan a la primera. Lo único que frena un POST es el `Origin` (CSRF),
// así que si algún día saliera un 403 es que otra web intentó disparar la
// acción desde el navegador de un visitante.
import { API, getJSON, postJSON } from "./api.js";

// ---------- Estado ----------

let serverOn = false; // estado real del servicio
let statusKnown = false; // ¿ya obtuvimos al menos una respuesta?
let statusError = null; // último error al consultar el estado
let fetchingStatus = false; // evita solicitudes de estado duplicadas
let fetchingLogs = false; // evita solicitudes de logs duplicadas
let logsOpen = false;
let alertTimer = null;

// ---------- Elementos ----------

const statusDot = document.getElementById("status-dot");
const statusSub = document.getElementById("status-sub");
const powerBtn = document.getElementById("power-btn");
const powerLabel = document.getElementById("power-label");
const restartBtn = document.getElementById("restart-btn");
const alertBox = document.getElementById("control-alert");

const logsCard = document.getElementById("logs-card");
const logsToggle = document.getElementById("logs-toggle");
const logsBody = document.getElementById("logs-body");
const logsList = document.getElementById("logs-list");
const logsCount = document.getElementById("logs-count");

// ---------- Utilidades ----------

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function showAlert(message) {
    alertBox.textContent = message;
    alertBox.hidden = false;
    clearTimeout(alertTimer);
    alertTimer = setTimeout(() => {
        alertBox.hidden = true;
    }, 8000);
}

// ---------- Estado del servidor ----------

function renderStatus() {
    if (!statusKnown) {
        // Sin estado conocido: los controles se deshabilitan en vez de fingir
        // uno que no tenemos (nada de "Apagar" en rojo sin efecto).
        statusDot.classList.remove("is-on");
        statusSub.textContent = statusError
            ? statusError
            : "No se pudo consultar el estado del servidor.";
        powerLabel.textContent = serverOn ? "Apagar" : "Encender";
        powerBtn.classList.remove("btn-stop");
        powerBtn.disabled = true;
        restartBtn.disabled = true;
        return;
    }

    statusDot.classList.toggle("is-on", serverOn);
    statusSub.textContent = serverOn
        ? "Servidor activo"
        : "Servidor inactivo";
    powerLabel.textContent = serverOn ? "Apagar" : "Encender";
    powerBtn.disabled = false;
    powerBtn.classList.toggle("btn-stop", serverOn);
    powerBtn.classList.toggle("btn-primary", !serverOn);
    restartBtn.disabled = false;
}

async function updateStatus() {
    if (fetchingStatus) {
        return; // evita condiciones de carrera
    }
    fetchingStatus = true;

    try {
        serverOn = Boolean(await getJSON(API.status));
        statusKnown = true;
        statusError = null;
    } catch (error) {
        // El bucle de polling no debe morir: registramos y seguimos. Un 502
        // (systemctl) también termina aquí y el error se muestra al usuario.
        statusKnown = false;
        statusError = error.message;
        console.error("No se pudo obtener el estado:", error);
    } finally {
        fetchingStatus = false;
        renderStatus();
    }
}

// ---------- Logs ----------

const LEVEL_CLASS = {
    INF: "level-INF",
    DBG: "level-DBG",
    WRN: "level-WRN",
    ERR: "level-ERR"
};

function renderLogs(logs) {
    logsList.textContent = "";

    if (!logs || logs.length === 0) {
        const empty = document.createElement("p");
        empty.className = "logs-state";
        empty.textContent = "No hay registros todavía.";
        logsList.appendChild(empty);
        logsCount.hidden = true;
        return;
    }

    // Conservar la posición de scroll si el usuario no está al final.
    const nearBottom =
        logsList.scrollHeight - logsList.scrollTop -
            logsList.clientHeight < 40;

    const fragment = document.createDocumentFragment();
    for (const log of logs) {
        const line = document.createElement("div");
        line.className = "log-line";

        const time = document.createElement("span");
        time.className = "log-time";
        time.textContent = log.time ?? "";

        const level = document.createElement("span");
        level.className =
            `log-level ${LEVEL_CLASS[log.level] || "level-other"}`;
        level.textContent = log.level ?? "?";

        const message = document.createElement("span");
        message.className = "log-message";
        message.textContent = log.message ?? "";

        line.append(time, level, message);
        fragment.appendChild(line);
    }
    logsList.appendChild(fragment);

    logsCount.textContent = String(logs.length);
    logsCount.hidden = false;

    if (nearBottom) {
        logsList.scrollTop = logsList.scrollHeight;
    }
}

function renderLogsLoading() {
    logsList.textContent = "";
    const loading = document.createElement("p");
    loading.className = "logs-state";
    loading.textContent = "Cargando registros…";
    logsList.appendChild(loading);
}

function renderLogsError(message) {
    logsList.textContent = "";
    const error = document.createElement("p");
    error.className = "logs-state is-error";
    error.textContent = `No se pudieron cargar los registros: ${message}`;
    logsList.appendChild(error);
}

async function updateLogs() {
    if (fetchingLogs) {
        return; // evita condiciones de carrera
    }
    fetchingLogs = true;

    try {
        const data = await getJSON(API.logs);
        renderLogs(data.logs);
    } catch (error) {
        console.error("No se pudieron obtener los logs:", error);
        renderLogsError(error.message);
    } finally {
        fetchingLogs = false;
    }
}

// ---------- Interacciones ----------

logsToggle.addEventListener("click", () => {
    logsOpen = !logsOpen;
    logsCard.classList.toggle("is-open", logsOpen);
    logsToggle.setAttribute("aria-expanded", String(logsOpen));
    logsBody.setAttribute("aria-hidden", String(!logsOpen));

    if (logsOpen) {
        renderLogsLoading();
        updateLogs();
    }
});

async function control(endpoint, gerund, infinitivo) {
    // Bloqueamos los controles mientras dure la petición.
    const spinner = document.createElement("span");
    spinner.className = "spinner";
    spinner.setAttribute("aria-hidden", "true");

    powerBtn.disabled = true;
    restartBtn.disabled = true;
    powerLabel.textContent = `${gerund}…`;
    powerBtn.appendChild(spinner);

    try {
        await postJSON(endpoint);
        await updateStatus();
    } catch (error) {
        showAlert(`No se pudo ${infinitivo} el servidor: ${error.message}`);
        await updateStatus();
    } finally {
        spinner.remove();
        renderStatus();
    }
}

powerBtn.addEventListener("click", () => {
    if (serverOn) {
        control(API.stop, "Apagando", "apagar");
    } else {
        control(API.start, "Encendiendo", "encender");
    }
});

restartBtn.addEventListener("click", () => {
    control(API.restart, "Reiniciando", "reiniciar");
});

// ---------- Bucle de polling ----------

// Una petición al entrar y otra al actuar (ver `control`); después solo lo
// necesario: el estado cada 15 s y los registros cada 5 s (únicamente con el
// panel abierto). Con la pestaña oculta no se pide nada y al volver se
// refresca de inmediato. Un error nunca mata el bucle en silencio.
const STATUS_MS = 15000;
const LOGS_MS = 5000;

let lastStatusAt = 0;

async function refreshLoop() {
    await updateStatus();
    lastStatusAt = Date.now();

    while (true) {
        if (!document.hidden) {
            if (Date.now() - lastStatusAt >= STATUS_MS) {
                await updateStatus();
                lastStatusAt = Date.now();
            }

            if (logsOpen) {
                await updateLogs();
            }
        }

        await sleep(LOGS_MS + Math.random() * 2000);
    }
}

document.addEventListener("visibilitychange", () => {
    // Al volver a la pestaña el estado puede estar desfasado: se adelanta
    // la próxima comprobación en vez de esperar al siguiente ciclo.
    if (!document.hidden) {
        lastStatusAt = 0;
    }
});

// El panel se carga directamente: no hay nada que ocultar ni que desbloquear.
refreshLoop();