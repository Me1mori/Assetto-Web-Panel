# Servicios

**¿FastAPI podrá ejecutar `systemctl`?**

La respuesta es **no**, al menos no directamente.

¿Por qué?

Porque tu servidor web se ejecutará como tu usuario (`USER`) y `systemctl start` normalmente requiere permisos administrativos.

Hay varias formas de solucionarlo:

1. Ejecutar FastAPI como root. ❌ (No recomendable.)

2. Usar `sudo` con una regla específica para permitir solo controlar `assettoserver.service`. ✅ (Recomendado.)
3. Usar PolicyKit (Polkit). También válido, pero más complejo.

- Yo eleguí la opción 2, porque es bastante estándar y más sensilla.

Con esa configuración, FastAPI podrá hacer:

```bash
sudo systemctl start assettoserver
sudo systemctl stop assettoserver
sudo systemctl restart assettoserver
sudo systemctl is-active assettoserver
```

Sin pedir contraseña, pero solo para ese servicio, no para cualquier comando del sistema.

---

## Paso 1. Instala la plantilla

En este repositorio hay una plantilla en `assettoserver.service` con marcadores
(`__USER__`, `__ACSERVER__`). Sustitúyelos e instálala:

```bash
sudo sed -e "s|__USER__|$USER|g" \
         -e "s|__ACSERVER__|/ruta/al/servidor|g" \
  backend/services/assettoserver.service \
  | sudo tee /etc/systemd/system/assettoserver.service >/dev/null
```

Si prefieres editarla a mano, cambia `__USER__` por tu usuario y `__ACSERVER__`
por la carpeta donde vive el servidor de juego (la que contiene el binario
`AssettoServer` y la carpeta `logs`).

## Paso 2. Recargar systemd

```bash
sudo systemctl daemon-reload
```

## Paso 3. Habilitarlo

Esto hace que pueda iniciarse automáticamente al arrancar el sistema (si quieres).

```bash
sudo systemctl enable assettoserver
```

## Paso 4. Probar

```bash
sudo systemctl start assettoserver
```

y luego

```bash
systemctl status assettoserver
```

Si todo está bien debería aparecer:

```
Active: active (running)
```
Luego prueva apagar

```bash
sudo systemctl stop assettoserver
```


## Paso 5. Crear la regla de sudo

Nunca edites `/etc/sudoers` directamente.

### Parte 1. Agegar comandos de usuario a sudoers

Abre:

```bash
sudo visudo -f /etc/sudoers.d/assettoserver
```

Y añade:

```text
__USER__ ALL=(root) NOPASSWD: \
    /usr/bin/systemctl start assettoserver, \
    /usr/bin/systemctl stop assettoserver, \
    /usr/bin/systemctl restart assettoserver, \
    /usr/bin/systemctl is-active assettoserver
```

Cambia `__USER__` por el nombre de tu usuario.

Esto significa:
- Solo el usuario `__USER__`.
- Solo esos cuatro comandos.
- Sin contraseña.
- No podrá ejecutar otros comandos como sudo rm -rf /.

> ⚠️ **Ojo:** si tu usuario ya tiene una línea tipo `(ALL) ALL` o
> `(ALL : ALL) ALL` en sudoers (muchas instalaciones de Raspberry Pi OS la
> traen de fábrica), esta regla no aporta seguridad real: ese usuario ya
> puede ser root sin contraseña. En ese caso lo razonable es dejar el panel en
> `127.0.0.1` detrás de un proxy inverso y no exponerlo a la red.

> ℹ️ El backend llama a `/usr/bin/sudo` y `/usr/bin/systemctl` con ruta
> absoluta a propósito, para no depender del `PATH` del proceso web.


### Parte 2. Probar desde la terminal

Ejecuta sin introducir contraseña:

```bash
sudo systemctl is-active assettoserver
```

Debe responder:

```
active
```

o

```
inactive
```

Y no pedir contraseña.

Prueba también los tres comandos que el panel usa (los cuatro de la regla):

```bash
sudo systemctl start assettoserver
sudo systemctl stop assettoserver
sudo systemctl restart assettoserver
```

Los tres deben responder sin pedir contraseña. Si alguno la pide, la regla de
sudoers no está bien puesta: revísala con `sudo -l`.