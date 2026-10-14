// Página de configuración (/config): sesiones, pista dinámica y cupo.
//
// Solo Sesiones, Pista dinámica y MAX_CLIENTS + AI_LEVEL. El resto de SERVER
// (PICKUP_MODE_ENABLED, LOOP_MODE, REGISTER_TO_LOBBY, LEGAL_TYRES, puertos…)
// sigue en la API pero no se muestra en la web. La pista y el clima viven en
// /map; los coches y las reglas en /cars.
import { API, getJSON, peekCache } from "./api.js";
import {
    collectUpdates, connectSaveButton, fillSimpleFields, makeAlert,
    saveConfigUpdates, setText
} from "./config-common.js";

const state = document.getElementById("config-state");
const form = document.getElementById("config-form");
const alertBox = document.getElementById("config-alert");

const showAlert = makeAlert(alertBox);
const saveBtn = connectSaveButton(form);

function fill(config) {
    fillSimpleFields(form, config, null);

    const server = config.SERVER || {};
    setText("servidor-nombre", server.NAME || "—");
    setText("servidor-pass", server.PASSWORD_SET ? "Configurada" : "Sin configurar");
    setText("servidor-admin", server.ADMIN_PASSWORD_SET ? "Configurada" : "Sin configurar");
}

async function cargar() {
    // Pintado instantáneo con lo precargado; luego revalidación silenciosa.
    const cached = peekCache(API.config);
    if (cached) {
        fill(cached);
        showContent();
        try {
            fill(await getJSON(API.config));
        } catch (error) {
            console.warn("Sin revalidar la configuración:", error);
        }
        return;
    }

    let config;
    try {
        config = await getJSON(API.config);
    } catch (error) {
        console.error("No se pudo cargar la configuración:", error);
        if (state) {
            state.textContent = `No se pudo cargar la configuración: ${error.message}`;
        }
        return;
    }
    fill(config);
    showContent();
}

function showContent() {
    if (state) {
        state.hidden = true;
    }
    if (form) {
        form.hidden = false;
    }
}

if (form) {
    form.addEventListener("submit", async event => {
        event.preventDefault();

        const updates = collectUpdates(form);

        if (Object.keys(updates).length === 0) {
            showAlert("Sin cambios que guardar.", false);
            return;
        }

        await saveConfigUpdates(API.config, updates, fill, showAlert, saveBtn);
    });
}

cargar();
