// Ayudas compartidas por las páginas de ajustes (/map, /cars, /config).
//
// Cada página tiene su propio script (map.js, cars.js, config.js) y todos
// importan de aquí: alertas, recolección de cambios y el botón Guardar de la
// cabecera. Las contraseñas nunca llegan del backend (solo banderas *_SET).
import { putJSON } from "./api.js";

export function escapeHtml(text) {
    return String(text ?? "").replace(/[&<>"']/g, c => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
}

export function setText(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = value;
    }
}

export function makeAlert(box) {
    let timer = null;
    return (message, ok) => {
        box.textContent = message;
        box.hidden = false;
        box.classList.toggle("is-ok", Boolean(ok));
        clearTimeout(timer);
        if (ok) {
            timer = setTimeout(() => {
                box.hidden = true;
            }, 6000);
        }
    };
}

// Recoge solo los campos que el usuario cambió (comparando con
// `data-initial`). Los Sí/No sin valor parten de "0" al rellenar, así que si
// no se tocan no se envían y el archivo no cambia.
export function collectUpdates(form) {
    const updates = {};
    const poner = (section, key, value) => {
        updates[section] = updates[section] || {};
        updates[section][key] = value;
    };

    for (const el of form.querySelectorAll("[data-section][data-key]")) {
        const value = el.value.trim();
        if (value === (el.dataset.initial ?? "")) {
            continue;
        }
        poner(el.dataset.section, el.dataset.key, value);
    }
    return updates;
}

// Rellena los campos simples (no clima) desde la config y guarda el valor
// inicial para detectar cambios. `skip` es un contenedor a ignorar
// (p. ej. las tarjetas de clima, que se reconstruyen aparte).
export function fillSimpleFields(form, config, skip) {
    for (const el of form.querySelectorAll("[data-section][data-key]")) {
        if (skip && skip.contains(el)) {
            continue;
        }
        const value = (config[el.dataset.section] || {})[el.dataset.key];
        el.value = value === undefined || value === null
            ? (el.tagName === "SELECT" ? "0" : "")
            : value;
        el.dataset.initial = el.value;
    }
}

export function markInitial(scope) {
    for (const el of scope.querySelectorAll("[data-section][data-key]")) {
        if (el.dataset.initial === undefined) {
            el.dataset.initial = el.value;
        }
    }
}

// Conecta el botón Guardar de la cabecera (`#save-top`, o el antiguo
// `#config-save-top`) con el envío del formulario. Devuelve el botón o null.
export function connectSaveButton(form) {
    const saveBtn = document.getElementById("save-top")
        || document.getElementById("config-save-top");
    if (saveBtn) {
        saveBtn.hidden = false;
        saveBtn.addEventListener("click", () => form.requestSubmit());
    }
    return saveBtn;
}

// Estado de carga del botón Guardar mientras dura el PUT.
export function setSaving(saveBtn, saving) {
    if (!saveBtn) {
        return null;
    }
    let spinner = saveBtn.querySelector(".spinner");
    if (saving) {
        const label = saveBtn.firstChild;
        if (label) {
            label.textContent = "Guardando…";
        }
        saveBtn.disabled = true;
        if (!spinner) {
            spinner = document.createElement("span");
            spinner.className = "spinner";
            spinner.setAttribute("aria-hidden", "true");
            saveBtn.appendChild(spinner);
        }
        return spinner;
    }
    if (spinner) {
        spinner.remove();
    }
    saveBtn.disabled = false;
    const label = saveBtn.firstChild;
    if (label) {
        label.textContent = "Guardar";
    }
    return null;
}

// Envía los cambios y rellena con la respuesta. Devuelve true si guardó.
export async function saveConfigUpdates(url, updates, fill, showAlert, saveBtn) {
    setSaving(saveBtn, true);
    try {
        fill(await putJSON(url, updates));
        showAlert("Guardado. Reinicia el servidor para aplicarlo.", true);
        return true;
    } catch (error) {
        console.error("No se pudo guardar la configuración:", error);
        showAlert(`No se pudo guardar: ${error.message}`, false);
        return false;
    } finally {
        setSaving(saveBtn, false);
    }
}

// ---------- Hora ----------
// SUN_ANGLE <-> HH:MM según la guía:
//   SUN_ANGLE = 16 * ((H*3600 + M*60 + S - 46800)) / (50400 - 46800)
export function solAMinutos(sol) {
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

export function minutosAHora(total) {
    const horas = String(Math.floor(total / 60)).padStart(2, "0");
    const minutos = String(total % 60).padStart(2, "0");
    return `${horas}:${minutos}`;
}

export function horaASol(texto) {
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
