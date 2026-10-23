# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y
versionado semántico.

## [0.2.0] - 2026-10-23

Mejoras de la revisión de la 0.1.0 (LABSMW-38). Sin cambios de variables que
rompan inventarios existentes, salvo los asserts nuevos.

### Cambiado

- NTP: se vigila la unit que está corriendo; si ninguna corre, la primera
  instalada. Antes podía vigilar un chrony instalado y parado y dar una falsa
  alerta.
- journald: el label `unit` se normaliza (`session-N.scope` → `session.scope`,
  `run-*`, `user@N.service`, scopes de contenedores, `sshd@…`,
  `systemd-coredump@…`). Reglas en `alloy_logs_journal_unit_rewrites`.
- Units sin sufijo en `alloy_systemd_units` se toman como `.service`. La
  existencia se comprueba con `systemctl show`, así `.timer`, `.mount` e
  instancias de templates ya no dan un aviso falso. El collector de systemd ya
  no descarta `.mount` ni `.scope` pedidos.
- Los avisos son warnings de Ansible (action plugin `mikroways_alloy_aviso`) y
  quedan en las custom stats `alloy_avisos`, visibles al final de la corrida
  con `ANSIBLE_SHOW_CUSTOM_STATS=true`.
- Ids de los archivos de log derivados de `name` o del `path`: reordenar
  `alloy_log_files` no pierde las posiciones de lectura. **Al actualizar desde
  0.1.0 cambian los ids**: cada archivo se vuelve a leer desde el final una vez
  (no se reenvía historial).
- Staging, backup de `conf.d` y la marca del textfile pasan a
  `/etc/alloy/.staging`, `/etc/alloy/.conf.d.prev` y
  `/etc/alloy/.textfile-created`, de root. Los de `/var/lib/alloy` se borran o
  migran.
- Las colecciones de las pruebas pasan de `meta/requirements.yml` a
  `molecule/requirements.yml`: Galaxy ya no las procesa para quienes consumen el
  rol.
- `robertdebock/galaxy-action` fijada por SHA (1.2.1).

### Corregido

- `--check` informaba `conf.d cambiaría: False` aunque la config fuera a
  cambiar.
- En la primera corrida, después del reinicio se mandaba además un reload por
  los secretos.
- Un paquete removido sin purgar (estado `rc`) se tomaba como instalado y el rol
  fallaba al habilitar el servicio.

### Agregado

- Assert: `alloy_extra_labels` no puede pisar `cliente`, `entorno`, `host` ni
  `os`.
- Asserts de `alloy_log_files`: `path` obligatorio, `name` válido e ids sin
  repetir.
- `tests/rol.yml`: render de ids, avisos visibles y empaquetado.

## [0.1.0] - 2026-10-23

Primera versión, solo Linux.

### Agregado

- Instalación de Alloy 1.21.1 desde el release de GitHub, con verificación de
  sha256, versión fija, `hold` en Debian/Ubuntu, mirror propio
  (`alloy_download_base_url`) y descarga en el controlador.
- Config en `/etc/alloy/conf.d/` generada en staging, validada con
  `alloy validate` y aplicada con `/-/reload`. Si Alloy no la carga, se
  restaura la anterior.
- Envío a Prometheus remote write y Loki push con auth `basic`, `bearer`,
  `header` u `oauth2`, por endpoint, con proxy y CA propia.
- Labels comunes `cliente`, `host`, `entorno` y `os` en todas las series y
  streams.
- Señales: métricas de host con allowlist, NTP, units de systemd, procesos,
  textfile (compatible con `mikroways.restic`), Teleport, logs de journald y de
  archivos filtrados por nivel, y self-monitoring.
- Desinstalación limpia con `alloy_state: absent`.
- Molecule con receptor falso (8 escenarios) y GitHub Actions con publicación
  en Galaxy.
