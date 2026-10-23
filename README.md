# mikroways.alloy

Rol de Ansible que instala [Grafana Alloy](https://grafana.com/docs/alloy/) en
hosts Linux y lo configura para enviar por push métricas y logs a un endpoint
configurable. Por defecto el endpoint es el gateway de ingesta de Mikroways,
pero el rol no sabe qué backend hay detrás: sirve igual para enviar directo a
Grafana Cloud o a cualquier Prometheus/Loki con remote write y push.

Qué envía:

- **Métricas de host** (node exporter integrado): CPU, carga, memoria, disco,
  filesystem, red, uptime y **NTP** (`timex`).
- **Estado de servicios** de systemd que tienen que estar activos y de
  **procesos** que no son units.
- **Textfile collector** en `/var/lib/node_exporter`, el mismo directorio que usa
  `mikroways.restic` para publicar sus métricas de backup.
- **Teleport**: si el host tiene `teleport.service`, vigila el servicio y, si el
  agente expone `diag_addr`, sus métricas (`process_state`).
- **Logs** de journald y de archivos, filtrados en el agente a warning/error
  (configurable).
- **Self-monitoring** de Alloy, para detectar cuando deja de enviar.

Todo lo que se envía pasa por una allowlist de métricas, para cuidar la
cardinalidad y no pasarse del free tier. Todas las series y streams llevan los
labels `cliente`, `host`, `entorno` y `os`.

## Requisitos

- ansible-core 2.19 o superior.
- Hosts soportados: Debian 11, 12 y 13; Ubuntu 20.04, 22.04 y 24.04; RHEL,
  Rocky, AlmaLinux y Oracle Linux 8, 9 y 10; Amazon Linux 2023 (sin CI).
- **Ubuntu 20.04** trae Python 3.8, que ansible-core 2.20 o superior no maneja.
  Para esos hosts, el playbook tiene que usar ansible-core 2.19.
- Salida HTTPS desde el host hasta el endpoint (directa o por proxy) y hasta
  GitHub para bajar el paquete (o ver `alloy_download_on_controller` y
  `alloy_download_base_url`).

## Instalación

```yaml
# requirements.yml
roles:
  - name: mikroways.alloy
    version: 0.1.0
```

```bash
ansible-galaxy install -r requirements.yml
```

## Cómo funciona

- **Instalación:** baja el `.deb` o el `.rpm` del
  [release de GitHub](https://github.com/grafana/alloy/releases) de la versión
  fijada en `alloy_version`, verifica su sha256 contra el `SHA256SUMS` del
  release y lo instala. No agrega repos de Grafana al host: un `apt upgrade` o
  `dnf upgrade` no cambia la versión. En Debian/Ubuntu, además, el paquete queda
  en `hold`. El paquete descargado se borra después de instalar.
- **Config:** un archivo `.alloy` por señal en `/etc/alloy/conf.d/`. El rol
  primero los genera en `/var/lib/alloy/staging/` y valida el conjunto con
  `alloy validate`. Si valida, respalda `conf.d/`, sincroniza y aplica la config
  con `/-/reload` (o arranca el servicio). **Si Alloy no carga la config
  nueva, el rol restaura la anterior y falla:** una config inválida nunca deja al
  host sin enviar.
- **Secretos:** van en `/etc/alloy/secrets/` (`root:alloy`, `0640`) y la config
  los lee por ruta. Nunca están en el archivo de config ni en la salida de
  Ansible (`no_log`).

## Variables

Las obligatorias con `alloy_state: present` son `alloy_labels_cliente`,
`alloy_labels_entorno` y `alloy_metrics_url` (y `alloy_logs_url` si hay logs
encendidos). El rol falla con un mensaje claro si falta alguna.

| Variable | Default | Descripción |
|---|---|---|
| `alloy_state` | `present` | `present` instala y configura; `absent` desinstala todo. |
| `alloy_version` | `1.21.1` | Versión fija de Alloy. `latest` no se acepta. |
| `alloy_download_base_url` | release de GitHub | Base de descarga; para un mirror interno con la misma estructura de rutas. |
| `alloy_download_on_controller` | `false` | Bajar el paquete en el controlador y copiarlo. |
| `alloy_metrics_url` | `""` | URL de Prometheus remote write. |
| `alloy_logs_url` | `""` | URL de Loki push. |
| `alloy_auth` | `{type: none}` | Auth común: `none`, `basic`, `bearer`, `header` u `oauth2` (ver ejemplos). |
| `alloy_metrics_auth` / `alloy_logs_auth` | `{}` | Campos que pisan `alloy_auth` para un solo endpoint. |
| `alloy_proxy_url` / `alloy_no_proxy` | `""` | Proxy de salida para los endpoints, el `token_url` y la descarga. |
| `alloy_tls_ca_pem` / `alloy_tls_ca_file` | `""` | CA propia, como PEM o como ruta en el host. |
| `alloy_tls_insecure_skip_verify` | `false` | No verificar el certificado (solo pruebas; el rol avisa). |
| `alloy_labels_cliente` / `alloy_labels_entorno` | `""` | Labels obligatorias. |
| `alloy_labels_host` | `inventory_hostname` | Label `host` (y `instance`). |
| `alloy_extra_labels` | `{}` | Labels extra en todas las series y streams. |
| `alloy_scrape_interval` | `60s` | Intervalo de scrape (cuida las DPM del free tier). |
| `alloy_host_metrics_enabled` | `true` | Métricas de host. |
| `alloy_unix_collectors` | lista corta | Collectors del node exporter (incluye `timex`). |
| `alloy_netdev_device_exclude` | `lo`, `veth*`, `docker*`, `br-*`, `cali*` | Interfaces que no se miden. |
| `alloy_metrics_allowlist_items` | ver `defaults/main.yml` | Nombres de métrica que se envían (regex por ítem). |
| `alloy_textfile_directory` | `/var/lib/node_exporter` | Directorio del textfile collector. |
| `alloy_textfile_allowlist` | `restic_.*\|kopia_.*\|backup_.*` | Métricas de textfile que se envían. |
| `alloy_systemd_units` | `[]` | Units que tienen que estar activas. |
| `alloy_systemd_restarts` | `false` | Enviar también `node_systemd_service_restart_total`. |
| `alloy_ntp_autodetect` | `true` | Detectar y vigilar chrony, timesyncd o ntpd. |
| `alloy_processes` | `[]` | Procesos a vigilar: `[{name, cmdline_regex}]`. |
| `alloy_teleport_enabled` | `auto` | `auto` (si existe `teleport.service`), `true` o `false`. |
| `alloy_teleport_diag_addr` | `""` | `diag_addr` del agente de Teleport, para sus métricas. |
| `alloy_logs_journal_enabled` | `true` | Logs de journald. |
| `alloy_logs_min_priority` | `warning` | Prioridad mínima: `emerg` … `debug`. |
| `alloy_logs_journal_max_age` | `12h` | Historial máximo en la primera corrida. |
| `alloy_log_files` | `[]` | Archivos: `[{path, labels, level_regex}]`. |
| `alloy_log_files_default_level_regex` | warn/error/crit… | Líneas que se envían si el ítem no define `level_regex`. |
| `alloy_self_monitoring_enabled` | `true` | Métricas del propio Alloy. |
| `alloy_extra_config_files` | `[]` | Archivos `.alloy` propios: `[{name, content}]`. |
| `alloy_extra_groups` | `[]` | Grupos extra para el usuario `alloy` (por ejemplo, para leer logs). |
| `alloy_remove_user` | `false` | En `absent`, borrar también el usuario y el grupo `alloy`. |

Labels de los logs: journald lleva `unit` y `level` (los keywords de Alloy:
`error`, `warning`, `crit`…); los archivos llevan `filename` y los `labels` del
ítem. El `job` es fijo por señal: `integrations/node_exporter`,
`integrations/process_exporter`, `integrations/teleport`, `integrations/alloy`,
`integrations/journal` e `integrations/logfile`.

## Ejemplos

### Host Linux enviando al gateway con API key

```yaml
- hosts: vms
  become: true
  roles:
    - role: mikroways.alloy
      vars:
        alloy_labels_cliente: acme
        alloy_labels_entorno: prod
        alloy_metrics_url: https://ingest.mikroways.net/api/prom/push
        alloy_logs_url: https://ingest.mikroways.net/loki/api/v1/push
        alloy_auth:
          type: header
          header_name: X-Api-Key
          header_value: "{{ vault_alloy_api_key }}"   # cifrado (vault o sops)
        alloy_systemd_units: [nginx.service, postgresql.service]
        alloy_log_files:
          - path: /var/log/nginx/error.log
            labels: {app: nginx}
```

### Gateway con OAuth2 (Keycloak)

```yaml
alloy_auth:
  type: oauth2
  oauth2:
    token_url: https://sso.mikroways.net/realms/ingest/protocol/openid-connect/token
    client_id: acme-vms
    client_secret: "{{ vault_alloy_client_secret }}"
    scopes: []
```

### Bastión con Teleport y NTP

NTP se detecta solo. Teleport también, si existe `teleport.service`. Para sus
métricas, el agente tiene que exponer `diag_addr` (en `mikroways.teleport`,
`teleport_diag_addr`).

```yaml
- hosts: bastions
  become: true
  roles:
    - role: mikroways.alloy
      vars:
        alloy_labels_cliente: acme
        alloy_labels_entorno: prod
        alloy_metrics_url: https://ingest.mikroways.net/api/prom/push
        alloy_logs_url: https://ingest.mikroways.net/loki/api/v1/push
        alloy_auth: {type: header, header_name: X-Api-Key, header_value: "{{ vault_alloy_api_key }}"}
        alloy_teleport_diag_addr: 127.0.0.1:3000
```

### Cliente con proxy y mirror interno

```yaml
alloy_proxy_url: http://proxy.acme.local:3128
alloy_no_proxy: localhost,127.0.0.1
# Mirror con la misma estructura que los releases de GitHub.
alloy_download_base_url: https://nexus.acme.local/repository/github-grafana-alloy
# O, si el host no llega ni al mirror:
# alloy_download_on_controller: true
```

### Envío directo a Grafana Cloud

En Grafana Cloud, métricas y logs tienen usuarios distintos (el id de cada
instancia) y comparten el token. Las claves que genera el alta de stacks se
mapean así:

| Alta de stacks (LABSMW-26) | Rol |
|---|---|
| `grafana_cloud_metrics_url` | `alloy_metrics_url` |
| `grafana_cloud_metrics_username` | `alloy_metrics_auth.username` |
| `grafana_cloud_logs_url` | `alloy_logs_url` |
| `grafana_cloud_logs_username` | `alloy_logs_auth.username` |
| `grafana_cloud_token` | `alloy_auth.password` |

```yaml
alloy_metrics_url: "{{ grafana_cloud_metrics_url }}"
alloy_logs_url: "{{ grafana_cloud_logs_url }}"
alloy_auth:
  type: basic
  password: "{{ grafana_cloud_token }}"
alloy_metrics_auth:
  username: "{{ grafana_cloud_metrics_username }}"
alloy_logs_auth:
  username: "{{ grafana_cloud_logs_username }}"
```

### Desinstalar

```yaml
alloy_state: absent
alloy_remove_user: true
```

Borra el paquete, `/etc/alloy`, el archivo de entorno, `/var/lib/alloy` y el
directorio de textfile solo si lo creó el rol.

## Antes de aplicar en un cliente

**Nunca se aplica en hosts de clientes sin mostrar antes el diff y tener
confirmación.** Primero:

```bash
ansible-playbook playbook.yml -l <host> --check --diff
```

En `--check` el rol muestra los cambios de la config (en staging) sin tocar el
servicio, y no muestra secretos. Recién con la confirmación se corre sin
`--check`.

## Desarrollo

```bash
uv sync
uv run yamllint . && uv run ansible-lint
uv run ansible-playbook -i tests/inventory tests/asserts.yml   # validaciones
uv run molecule test -s default                               # o cualquier escenario
```

Escenarios de Molecule (contenedores con systemd y un receptor falso con
Prometheus, Loki, nginx con auth/TLS y tinyproxy):

| Escenario | Qué prueba |
|---|---|
| `default` | Todas las señales con basic auth y CA propia, config rota rechazada, rotación de password. Debian 12, Ubuntu 22.04/24.04, Rocky 8/9. |
| `version` | Downgrade manual: el rol vuelve a la versión fijada y deja el `hold`. |
| `auth-bearer`, `auth-header`, `auth-oauth2` | Cada modo de autenticación. |
| `proxy` | Host sin salida directa: todo por tinyproxy y paquete bajado en el controlador. |
| `teleport` | Detección del agente y scrape de su `diag_addr`. |
| `absent` | Desinstalación limpia e idempotente. |

Con podman en lugar de Docker:
`export DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock`.

## Licencia

MIT
