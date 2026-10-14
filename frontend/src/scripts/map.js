// Página del mapa (/map): pista, hora del día y clima.
//
// Muestra TRACK + CONFIG_TRACK (con lista de pistas instaladas), la hora en
// 24 h convertida a SUN_ANGLE al guardar, TIME_OF_DAY_MULT y los tramos de
// clima con presets en español. Guarda con PUT /api/server/config.
import { API, getJSON, peekCache, putJSON } from "./api.js";
import {
    collectUpdates, connectSaveButton, escapeHtml, fillSimpleFields,
    horaASol, makeAlert, markInitial, minutosAHora, saveConfigUpdates,
    setText, solAMinutos
} from "./config-common.js";

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

const state = document.getElementById("map-state");
const form = document.getElementById("map-form");
const alertBox = document.getElementById("map-alert");
const horaInput = document.getElementById("hora-input");
const horaSol = document.getElementById("hora-sol-valor");
const weatherCards = document.getElementById("weather-cards");
const weatherAdd = document.getElementById("weather-add");
const trackList = document.getElementById("track-list");

const showAlert = makeAlert(alertBox);
const saveBtn = connectSaveButton(form);

let presets = [];
let weatherSections = [];
let horaInicial = null;
let solLiteral = null;

// ---------- Hora ----------

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
    fillSimpleFields(form, config, weatherCards);

    // La hora se edita en 24 h y se convierte a SUN_ANGLE al guardar.
    const server = config.SERVER || {};
    solLiteral = server.SUN_ANGLE ?? null;
    const minutos = solAMinutos(server.SUN_ANGLE);
    horaInicial = minutos === null ? "" : minutosAHora(minutos);
    if (horaInput) {
        horaInput.value = horaInicial;
    }
    updateHora();

    buildWeatherCards(config);
}

function fillTracks(trks) {
    if (trackList && trks && Array.isArray(trks.tracks)) {
        trackList.textContent = "";
        for (const track of trks.tracks) {
            const option = document.createElement("option");
            option.value = track.name;
            trackList.appendChild(option);
        }
    }
}

function showContent() {
    if (state) {
        state.hidden = true;
    }
    if (form) {
        form.hidden = false;
    }
}

async function cargar() {
    // Pintado instantáneo: si la precarga ya guardó datos, se muestran sin
    // pasar por "Cargando mapa…" y luego se revalidan en segundo plano.
    const cachedConfig = peekCache(API.config);
    if (cachedConfig) {
        presets = [];
        const cachedPres = peekCache(API.presets);
        if (cachedPres && Array.isArray(cachedPres.presets)) {
            presets = cachedPres.presets;
        }
        fillTracks(peekCache(API.tracks));
        fill(cachedConfig);
        showContent();
        // Revalidación silenciosa: actualiza sin parpadear.
        revalidar();
        return;
    }

    let config;
    try {
        const [cfg, pres, trks] = await Promise.all([
            getJSON(API.config),
            getJSON(API.presets).catch(error => {
                console.warn("Sin lista de presets:", error);
                return { presets: [] };
            }),
            getJSON(API.tracks).catch(error => {
                console.warn("Sin lista de pistas:", error);
                return { tracks: [] };
            })
        ]);
        config = cfg;
        presets = Array.isArray(pres.presets) ? pres.presets : [];
        fillTracks(trks);
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

async function revalidar() {
    try {
        const [cfg, pres, trks] = await Promise.all([
            getJSON(API.config),
            getJSON(API.presets).catch(() => null),
            getJSON(API.tracks).catch(() => null)
        ]);
        if (pres && Array.isArray(pres.presets)) {
            presets = pres.presets;
        }
        if (trks) {
            fillTracks(trks);
        }
        fill(cfg);
    } catch (error) {
        // Se sigue mostrando lo cacheado; el error solo va a consola.
        console.warn("Sin revalidar el mapa:", error);
    }
}

if (horaInput) {
    horaInput.addEventListener("input", updateHora);
}

if (form) {
    form.addEventListener("submit", async event => {
        event.preventDefault();

        const updates = collectUpdates(form);

        // La hora solo viaja si cambió, convertida a SUN_ANGLE.
        if (horaInput && horaInput.value !== horaInicial) {
            const sol = horaASol(horaInput.value);
            if (sol === null) {
                showAlert("Hora inválida: usa el formato 24 h HH:MM.", false);
                return;
            }
            updates.SERVER = updates.SERVER || {};
            updates.SERVER.SUN_ANGLE = sol;
        }

        if (Object.keys(updates).length === 0) {
            showAlert("Sin cambios que guardar.", false);
            return;
        }

        await saveConfigUpdates(API.config, updates, fill, showAlert, saveBtn);
    });
}

cargar();
