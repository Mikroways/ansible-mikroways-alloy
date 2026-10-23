# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y
versionado semántico.

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
