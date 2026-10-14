// Página de coches (/cars): inscritos de entry_list.ini + reglas.
//
// Los coches se agrupan por MODEL con su conteo; por plaza solo se edita
// MODEL y SKIN (con la lista de instalados cuando existe). GUID, DRIVERNAME y
// TEAM nunca llegan del backend. Las reglas son campos simples de SERVER que
// se guardan con PUT /api/server/config, mientras que los coches usan
// PUT /api/server/entry-list. El botón Guardar envía ambos si cambiaron.
import { API, getJSON, peekCache, putJSON } from "./api.js";
import {
    collectUpdates, connectSaveButton, escapeHtml, fillSimpleFields,
    makeAlert, setSaving, setText
} from "./config-common.js";

const state = document.getElementById("cars-state");
const form = document.getElementById("cars-form");
const alertBox = document.getElementById("cars-alert");
const groupsBox = document.getElementById("cars-groups");
const totalBox = document.getElementById("cars-total");

const showAlert = makeAlert(alertBox);
const saveBtn = connectSaveButton(form);

let available = [];
let initialCars = [];

function skinsFor(model) {
    const found = available.find(item => item.model === model);
    return found ? found.skins : [];
}

function modelControl(index, model) {
    if (available.length === 0) {
        return `<input class="field-input mono" type="text" data-cmodel="${index}" value="${escapeHtml(model)}">`;
    }
    const known = available.some(item => item.model === model);
    const options = known || model === ""
        ? available
        : [{ model, skins: [] }, ...available];
    return `<select class="field-input mono" data-cmodel="${index}">` +
        options.map(item =>
            `<option value="${escapeHtml(item.model)}"${item.model === model ? " selected" : ""}>${escapeHtml(item.model)}</option>`
        ).join("") +
        `</select>`;
}

function skinControl(index, model, skin) {
    const skins = skinsFor(model);
    if (available.length === 0 || skins.length === 0) {
        return `<input class="field-input mono" type="text" data-cskin="${index}" value="${escapeHtml(skin)}" list="skin-list-${index}">` +
            `<datalist id="skin-list-${index}">` +
            `<option value="auto"></option>` +
            skins.map(name => `<option value="${escapeHtml(name)}"></option>`).join("") +
            `</datalist>`;
    }
    const known = skin === "auto" || skins.includes(skin);
    const options = known ? skins : [skin, ...skins];
    return `<select class="field-input mono" data-cskin="${index}">` +
        `<option value="auto"${skin === "auto" ? " selected" : ""}>auto (aleatoria)</option>` +
        options.filter(name => name !== "auto").map(name =>
            `<option value="${escapeHtml(name)}"${name === skin ? " selected" : ""}>${escapeHtml(name)}</option>`
        ).join("") +
        `</select>`;
}

function buildGroups(cars) {
    groupsBox.textContent = "";

    const order = [];
    const byModel = new Map();
    for (const car of cars) {
        if (!byModel.has(car.model)) {
            byModel.set(car.model, []);
            order.push(car.model);
        }
        byModel.get(car.model).push(car);
    }

    for (const model of order) {
        const group = document.createElement("div");
        group.className = "car-group";
        group.dataset.model = model;

        const list = byModel.get(model);
        const rows = list.map(car => `
            <div class="car-row">
                <div class="field-row">
                    <label class="field">
                        <span class="field-label">Plaza ${car.index} · Modelo</span>
                        ${modelControl(car.index, car.model)}
                    </label>
                    <label class="field">
                        <span class="field-label">Skin</span>
                        ${skinControl(car.index, car.model, car.skin)}
                    </label>
                </div>
            </div>`).join("");

        group.innerHTML =
            `<div class="tramo-head">` +
            `<h3 class="tramo-title">${escapeHtml(model)} · ${list.length}</h3>` +
            `</div>` + rows;
        groupsBox.appendChild(group);
    }

    // Al cambiar de modelo se actualiza su lista de skins.
    for (const modelEl of groupsBox.querySelectorAll("[data-cmodel]")) {
        modelEl.addEventListener("change", () => {
            const index = Number(modelEl.dataset.cmodel);
            const card = modelEl.closest(".car-row");
            const skinSlot = card.querySelector("[data-cskin]");
            const fresh = document.createElement("div");
            fresh.innerHTML = skinControl(index, modelEl.value, "auto");
            skinSlot.replaceWith(fresh.firstChild);
        });
    }
}

function fillEntry(entries) {
    const cars = Array.isArray(entries.cars) ? entries.cars : [];
    initialCars = cars.map(car => ({ ...car }));
    buildGroups(cars);
    if (totalBox) {
        totalBox.textContent = `${entries.total ?? cars.length} plazas`;
    }
}

function fillRules(config) {
    fillSimpleFields(form, config, null);
    const server = config.SERVER || {};
    setText("coches-valor", server.CARS || "—");
}

function collectCarUpdates() {
    const cars = [];
    const models = groupsBox.querySelectorAll("[data-cmodel]");
    for (const modelEl of models) {
        const index = Number(modelEl.dataset.cmodel);
        const row = modelEl.closest(".car-row");
        const skinEl = row.querySelector("[data-cskin]");
        const model = modelEl.value.trim();
        const skin = skinEl.value.trim();
        const initial = initialCars.find(car => car.index === index);
        if (initial && initial.model === model && initial.skin === skin) {
            cars[index] = { model: initial.model, skin: initial.skin };
            continue;
        }
        cars[index] = { model, skin };
    }
    const initialByIndex = new Map(initialCars.map(car => [car.index, car]));
    const changed = cars.some((car, index) => {
        const before = initialByIndex.get(index);
        return !before || before.model !== car.model || before.skin !== car.skin;
    });
    return { cars, changed };
}

async function cargar() {
    // Pintado instantáneo con lo precargado; luego revalidación silenciosa.
    const cachedConfig = peekCache(API.config);
    const cachedEntries = peekCache(API.entryList);
    if (cachedConfig && cachedEntries) {
        const cachedAvail = peekCache(API.availableCars);
        available = cachedAvail && Array.isArray(cachedAvail.models)
            ? cachedAvail.models
            : [];
        fillRules(cachedConfig);
        fillEntry(cachedEntries);
        showContent();
        revalidar();
        return;
    }

    try {
        const [cfg, entries, avail] = await Promise.all([
            getJSON(API.config),
            getJSON(API.entryList),
            getJSON(API.availableCars).catch(error => {
                console.warn("Sin lista de modelos:", error);
                return { models: [] };
            })
        ]);
        available = Array.isArray(avail.models) ? avail.models : [];
        fillRules(cfg);
        fillEntry(entries);
    } catch (error) {
        console.error("No se pudieron cargar los coches:", error);
        if (state) {
            state.textContent = `No se pudieron cargar los coches: ${error.message}`;
        }
        return;
    }
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

async function revalidar() {
    try {
        const [cfg, entries, avail] = await Promise.all([
            getJSON(API.config),
            getJSON(API.entryList),
            getJSON(API.availableCars).catch(() => null)
        ]);
        if (avail && Array.isArray(avail.models)) {
            available = avail.models;
        }
        fillRules(cfg);
        fillEntry(entries);
    } catch (error) {
        console.warn("Sin revalidar los coches:", error);
    }
}

if (form) {
    form.addEventListener("submit", async event => {
        event.preventDefault();

        const ruleUpdates = collectUpdates(form);
        const { cars, changed } = collectCarUpdates();

        if (Object.keys(ruleUpdates).length === 0 && !changed) {
            showAlert("Sin cambios que guardar.", false);
            return;
        }

        setSaving(saveBtn, true);
        try {
            if (changed) {
                fillEntry(await putJSON(API.entryList, { cars }));
            }
            if (Object.keys(ruleUpdates).length > 0) {
                const { putJSON: putCfg } = await import("./api.js");
                fillRules(await putCfg(API.config, ruleUpdates));
            }
            showAlert("Guardado. Reinicia el servidor para aplicarlo.", true);
        } catch (error) {
            console.error("No se pudo guardar:", error);
            showAlert(`No se pudo guardar: ${error.message}`, false);
        } finally {
            setSaving(saveBtn, false);
        }
    });
}

cargar();
