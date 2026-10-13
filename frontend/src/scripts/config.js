// Página de configuración (/config).
//
// Muestra server_cfg.ini en un formulario y guarda los cambios con
// PUT /api/server/config. Solo se envían los campos que el usuario cambió;
// las contraseñas nunca llegan del backend (solo banderas *_SET).
import { API, getJSON, putJSON } from "./api.js";

// Tipos oficiales de WeatherFX (assettoserver.org/docs/misc/wfx-types),
// con nombre en español para la web (el original va entre paréntesis).
const WFX_TYPES = [
    ["LightThunderstorm", "Tormenta eléctrica ligera"],
    ["Thunderstorm", "Tormenta eléctrica"],
    ["HeavyThunderstorm", "Tormenta eléctrica fuerte"],
    ["LightDrizzle", "Llovizna ligera"],
    ["Drizzle", "Llovizna"],
    ["HeavyDrizzle", "Llovizna fuerte"],
    ["LightRain", "Lluvia ligera"],
    ["Rain", "Lluvia"],
    ["HeavyRain", "Lluvia fuerte"],
    ["LightSnow", "Nieve ligera"],
    ["Snow", "Nieve"],
    ["HeavySnow", "Nieve fuerte"],
    ["LightSleet", "Aguanieve ligera"],
    ["Sleet", "Aguanieve"],
    ["HeavySleet", "Aguanieve fuerte"],
    ["Clear", "Despejado"],
    ["FewClouds", "Pocas nubes"],
    ["ScatteredClouds", "Nubes dispersas"],
    ["BrokenClouds", "Nubes fragmentadas"],
    ["OvercastClouds", "Cubierto"],
    ["Fog", "Niebla"],
    ["Mist", "Neblina"],
    ["Smoke", "Humo"],
    ["Haze", "Calima"],
    ["Sand", "Arena"],
    ["Dust", "Polvo"],
    ["Squalls", "Chubascos"],
    ["Tornado", "Tornado"],
    ["Hurricane", "Huracán"],
    ["Cold", "Frío"],
    ["Hot", "Calor"],
    ["Windy", "Ventoso"],
    ["Hail", "Granizo"]
];

// Campos numéricos de cada tramo, con etiqueta y límites del input.
const WEATHER_NUMERIC = [
    ["BASE_TEMPERATURE_AMBIENT", "Ambiente °C", -20, 60],
    ["BASE_TEMPERATURE_ROAD", "Pista °C", -20, 80],
    ["VARIATION_AMBIENT", "Var. ambiente", 0, 30],
    ["VARIATION_ROAD", "Var. pista", 0, 30],
    ["WIND_BASE_SPEED_MIN", "Viento mín.", 0, 200],
    ["WIND_BASE_SPEED_MAX", "Viento máx.", 0, 200],
    ["WIND_BASE_DIRECTION", "Dirección °", 0, 360],
    ["WIND_VARIATION_DIRECTION", "Var. dirección °", 0, 360]
];

const state = document.getElementById("config-state");
const form = document.getElementById("config-form");
const grid = document.getElementById("config-grid");
const saveBtn = document.getElementById("config-save-top");
const alertBox = document.getElementById("config-alert");
const horaInput = document.getElementById("hora-input");
const horaSol = document.getElementById("hora-sol-valor");
const weatherCards = document.getElementById("weather-cards");
const weatherAdd = document.getElementById("weather-add");

let presets = [];
let weatherSections = [];

// ---------- Utilidades ----------

function escapeHtml(text) {
    return String(text ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = value;
    }
}

let alertTimer = null;

function showAlert(message, ok) {
    alertBox.textContent = message;
    alertBox.hidden = false;
    alertBox.classList.toggle("is-ok", Boolean(ok));
    clearTimeout(alertTimer);
    if (ok) {
        alertTimer = setTimeout(() => {
            alertBox.hidden = true;
        }, 6000);
    }
}

// ---------- Hora ----------
// SUN_ANGLE <-> HH:MM según la guía:
//   SUN_ANGLE = 16 * ((H*3600 + M*60 + S - 46800)) / (50400 - 46800)
function solAMinutos(sol) {
    const angulo = Number(sol);
    if (sol === "" || sol === null || sol === undefined || Number.isNaN(angulo)) {
        return null;
    }
    const segundos = Math.round(angulo * 225 + 46800);
    if (segundos < 0 || segundos >= 86400) {
        return null;
    }
    return Math.floor(segundos / 60);
}

function minutosAHora(total) {
    const horas = String(Math.floor(total / 60)).padStart(2, "0");
    const minutos = String(total % 60).padStart(2, "0");
    return `${horas}:${minutos}`;
}

function horaASol(texto) {
    const match = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/.exec(texto.trim());
    if (!match) {
        return null;
    }
    const horas = Number(match[1]);
    const minutos = Number(match[2]);
    const segundos = Number(match[3] || 0);
    if (horas > 23 || minutos > 59 || segundos > 59) {
        return null;
    }
    const total = horas * 3600 + minutos * 60 + segundos;
    return String(Math.round((16 * (total - 46800) / 3600) * 100) / 100);
}

let horaInicial = null;
let solLiteral = null;

function updateHora() {
    if (!horaInput || !horaSol) {
        return;
    }
    // Sin tocar: se muestra el valor literal del archivo, no un recálculo
    // que podría diferir por el redondeo a minutos.
    if (horaInput.value === horaInicial) {
        horaSol.textContent = solLiteral === null ? "…" : solLiteral;
        return;
    }
    const sol = horaASol(horaInput.value);
    horaSol.textContent = sol === null ? "…" : sol;
}

// ---------- Clima dinámico ----------

// "6_mid_clouds=0" o "sol_03_scattered_clouds_type=8" -> {preset, type}.
function splitGraphics(graphics) {
    const match = /^(.*?)(?:_type)?=(\d+)\s*$/.exec((graphics || "").trim());
    if (match) {
        return { preset: match[1], type: match[2] };
    }
    return { preset: (graphics || "").trim(), type: "" };
}

function markInitial(scope) {
    for (const el of scope.querySelectorAll("[data-section][data-key]")) {
        if (el.dataset.initial === undefined) {
            el.dataset.initial = el.value;
        }
    }
}

function weatherIndex(section) {
    return Number(section.split("_")[1]);
}

function syncGraphics(card) {
    const preset = card.querySelector("[data-wpreset]").value.trim();
    const type = card.querySelector("[data-wtype]").value;
    const hidden = card.querySelector("[data-section][data-key='GRAPHICS']");
    hidden.value = type === "" ? preset : `${preset}_type=${type}`;
}

function buildWeatherCard(section, values, isNew) {
    const { preset, type } = splitGraphics(values.GRAPHICS || "");
    const numero = weatherIndex(section);

    const card = document.createElement("div");
    card.className = "weather-tramo";
    card.dataset.wsection = section;

    let presetControl;
    if (presets.length > 0) {
        const known = presets.some(item => item.name === preset);
        const opciones = known || preset === ""
            ? presets
            : [{ name: preset, label: preset }, ...presets];
        presetControl = `<select class="field-input mono" data-wpreset>` +
            opciones.map(item => {
                const texto = item.label === item.name
                    ? item.name
                    : `${item.label} (${item.name})`;
                return `<option value="${escapeHtml(item.name)}"${item.name === preset ? " selected" : ""}>${escapeHtml(texto)}</option>`;
            }).join("") +
            `</select>`;
    } else {
        presetControl = `<input class="field-input mono" type="text" data-wpreset value="${escapeHtml(preset)}">`;
    }

    const typeOptions = `<option value="">—</option>` + WFX_TYPES.map(([en, es], id) =>
        `<option value="${id}"${String(id) === type ? " selected" : ""}>${id} · ${es} (${en})</option>`
    ).join("");

    const numeric = WEATHER_NUMERIC.map(([key, label, min, max]) => `
        <label class="field">
            <span class="field-label">${label}</span>
            <input class="field-input" type="number" min="${min}" max="${max}"
                data-section="${section}" data-key="${key}"
                value="${escapeHtml(values[key] ?? "")}">
        </label>`).join("");

    card.innerHTML =
        `<div class="tramo-head">` +
        `<h3 class="tramo-title">Tramo ${numero}</h3>` +
        `<button class="btn btn-ghost btn-sm" type="button" data-del="${section}">Borrar</button>` +
        `</div>` +
        `<input type="hidden" data-section="${section}" data-key="GRAPHICS" value="${escapeHtml(values.GRAPHICS || "")}">` +
        `<div class="field-row">` +
        `<label class="field"><span class="field-label">Visual (preset)</span>${presetControl}</label>` +
        `<label class="field"><span class="field-label">Tipo WeatherFX</span>` +
        `<select class="field-input" data-wtype>${typeOptions}</select></label>` +
        `</div>` +
        `<div class="field-row">${numeric}</div>`;

    // Un tramo nuevo cuenta como cambiado entero para que se cree al guardar.
    if (isNew) {
        for (const el of card.querySelectorAll("[data-section][data-key]")) {
            el.dataset.initial = "";
        }
    } else {
        markInitial(card);
    }

    card.querySelector("[data-wpreset]").addEventListener("change", () => syncGraphics(card));
    card.querySelector("[data-wtype]").addEventListener("change", () => syncGraphics(card));
    card.querySelector("[data-del]").addEventListener("click", () => borrarTramo(section));

    return card;
}

function refreshDeleteButtons() {
    const cards = weatherCards.querySelectorAll(".weather-tramo");
    for (const btn of weatherCards.querySelectorAll("[data-del]")) {
        btn.disabled = cards.length <= 1;
        btn.title = cards.length <= 1
            ? "Debe quedar al menos un tramo"
            : `Borrar el ${btn.dataset.del}`;
    }
}

function buildWeatherCards(config) {
    weatherCards.textContent = "";
    weatherSections = Object.keys(config)
        .filter(section => /^WEATHER_\d+$/.test(section))
        .sort((a, b) => weatherIndex(a) - weatherIndex(b));
    for (const section of weatherSections) {
        weatherCards.appendChild(buildWeatherCard(section, config[section] || {}, false));
    }
    refreshDeleteButtons();
    weatherCards.setAttribute("aria-busy", "false");
}

async function borrarTramo(section) {
    if (weatherCards.querySelectorAll(".weather-tramo").length <= 1) {
        showAlert("Debe quedar al menos un tramo de clima.", false);
        return;
    }
    const numero = weatherIndex(section);
    if (!window.confirm(`¿Borrar el tramo ${numero}? Los siguientes se renumeran.`)) {
        return;
    }
    try {
        fill(await putJSON(API.config, { [section]: null }));
        showAlert(`Tramo ${numero} borrado. Reinicia el servidor para aplicarlo.`, true);
    } catch (error) {
        console.error("No se pudo borrar el tramo:", error);
        showAlert(`No se pudo borrar: ${error.message}`, false);
    }
}

if (weatherAdd) {
    weatherAdd.addEventListener("click", () => {
        const next = weatherSections.length > 0
            ? Math.max(...weatherSections.map(weatherIndex)) + 1
            : 0;
        const section = `WEATHER_${next}`;
        // Clona el último tramo: valores ya válidos como punto de partida.
        const last = weatherSections.length > 0
            ? weatherSections[weatherSections.length - 1]
            : null;
        const base = {};
        if (last) {
            const card = weatherCards.querySelector(`[data-wsection="${last}"]`);
            for (const el of card.querySelectorAll("[data-section][data-key]")) {
                base[el.dataset.key] = el.value;
            }
        } else {
            base.GRAPHICS = "sol_03_scattered_clouds_type=17";
            for (const [key] of WEATHER_NUMERIC) {
                base[key] = "0";
            }
        }
        weatherSections.push(section);
        weatherCards.appendChild(buildWeatherCard(section, base, true));
        refreshDeleteButtons();
    });
}

// ---------- Relleno general ----------

function fill(config) {
    const server = config.SERVER || {};
    for (const el of form.querySelectorAll("[data-section][data-key]")) {
        if (el.closest("#weather-cards")) {
            continue; // el clima se reconstruye abajo
        }
        const value = (config[el.dataset.section] || {})[el.dataset.key];
        // Los Sí/No sin valor en el archivo parten de "0" para no inventar
        // nada: si no se tocan, no se envían y el archivo no cambia.
        el.value = value === undefined || value === null ? (el.tagName === "SELECT" ? "0" : "") : value;
        el.dataset.initial = el.value;
    }

    // La hora se edita en 24 h y se convierte a SUN_ANGLE al guardar.
    solLiteral = server.SUN_ANGLE ?? null;
    const minutos = solAMinutos(server.SUN_ANGLE);
    horaInicial = minutos === null ? "" : minutosAHora(minutos);
    if (horaInput) {
        horaInput.value = horaInicial;
    }
    updateHora();

    setText("servidor-pass", server.PASSWORD_SET ? "Configurada" : "Sin configurar");
    setText("servidor-admin", server.ADMIN_PASSWORD_SET ? "Configurada" : "Sin configurar");
    setText("servidor-nombre", server.NAME || "—");
    setText("coches-valor", server.CARS || "—");

    buildWeatherCards(config);

    if (grid) {
        grid.setAttribute("aria-busy", "false");
    }
}

async function cargar() {
    let config;
    try {
        const [cfg, pres] = await Promise.all([
            getJSON(API.config),
            getJSON(API.presets).catch(error => {
                console.warn("Sin lista de presets:", error);
                return { presets: [] };
            })
        ]);
        config = cfg;
        presets = Array.isArray(pres.presets) ? pres.presets : [];
    } catch (error) {
        console.error("No se pudo cargar la configuración:", error);
        if (state) {
            state.textContent = `No se pudo cargar la configuración: ${error.message}`;
        }
        return;
    }
    fill(config);
    if (state) {
        state.hidden = true;
    }
    if (form) {
        form.hidden = false;
    }
    if (saveBtn) {
        saveBtn.hidden = false;
        saveBtn.addEventListener("click", () => form.requestSubmit());
    }
}

if (horaInput) {
    horaInput.addEventListener("input", updateHora);
}

if (form) {
    form.addEventListener("submit", async event => {
        event.preventDefault();

        const updates = {};
        const poner = (section, key, value) => {
            updates[section] = updates[section] || {};
            updates[section][key] = value;
        };

        for (const el of form.querySelectorAll("[data-section][data-key]")) {
            const value = el.value.trim();
            if (value === (el.dataset.initial ?? "")) {
                continue; // sin tocar: el archivo no cambia
            }
            poner(el.dataset.section, el.dataset.key, value);
        }

        // La hora solo viaja si cambió, convertida a SUN_ANGLE.
        if (horaInput && horaInput.value !== horaInicial) {
            const sol = horaASol(horaInput.value);
            if (sol === null) {
                showAlert("Hora inválida: usa el formato 24 h HH:MM.", false);
                return;
            }
            poner("SERVER", "SUN_ANGLE", sol);
        }

        if (Object.keys(updates).length === 0) {
            showAlert("Sin cambios que guardar.", false);
            return;
        }

        const label = saveBtn ? saveBtn.firstChild : null;
        const spinner = document.createElement("span");
        spinner.className = "spinner";
        spinner.setAttribute("aria-hidden", "true");
        if (saveBtn) {
            saveBtn.disabled = true;
        }
        if (label) {
            label.textContent = "Guardando…";
        }
        if (saveBtn) {
            saveBtn.appendChild(spinner);
        }

        try {
            fill(await putJSON(API.config, updates));
            showAlert("Guardado. Reinicia el servidor para aplicarlo.", true);
        } catch (error) {
            console.error("No se pudo guardar la configuración:", error);
            showAlert(`No se pudo guardar: ${error.message}`, false);
        } finally {
            spinner.remove();
            if (saveBtn) {
                saveBtn.disabled = false;
            }
            if (label) {
                label.textContent = "Guardar";
            }
        }
    });
}

cargar();
