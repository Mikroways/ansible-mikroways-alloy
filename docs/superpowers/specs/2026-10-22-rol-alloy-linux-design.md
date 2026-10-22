---
title: Rol de Ansible mikroways.alloy (v1, Linux)
issue: LABSMW-34
fecha: 2026-10-22
estado: aprobado por Christian Rodriguez (2026-10-22), con los cambios de repo, NTP y Teleport
---

## Intención

Mikroways quiere enterarse antes que el cliente cuando una VM o un bastión anda
mal. Para eso, un rol de Ansible instala Grafana Alloy en el host y envía por
push métricas y logs a un endpoint configurable. Por defecto ese endpoint es el
API gateway de ingesta de Mikroways (LABSMW-33), que oculta el backend (Grafana
Cloud por cliente) y maneja sus credenciales. El rol no sabe qué backend hay
detrás.

El rol tiene que poder aplicarse en lote a muchos clientes, ser curado (envía
solo lo necesario para no pasarse del free tier) y estar versionado.

## Objetivos, no objetivos y anti-objetivos

**Objetivos (v1)**

- Instalar, configurar, actualizar y desinstalar Alloy en Ubuntu, Debian y
  RHEL-like, que son los SO que vemos en clientes.
- Enviar: métricas de host, estado de servicios systemd y procesos, métricas de
  textfile (backups), logs de journald y de archivos filtrados a warning/error,
  y métricas del propio Alloy.
- Que endpoint, autenticación, proxy y TLS sean variables.
- Labels comunes `cliente`, `host`, `entorno` y `os` en todas las series y
  streams, más extras por variable.
- Rol idempotente (la segunda corrida da 0 cambios), probado con Molecule
  contra un receptor local, con CI en GitHub Actions y versionado semántico.

**No objetivos (v1)**

- Windows. La v1 deja la estructura preparada (tareas por SO, variables
  independientes del SO) pero no lo implementa. Lo decidió Christian en el
  issue.
- Integrar el rol a los playbooks del repo `bootstrap` de cada cliente (bastión
  y resources). Eso lo ve Juan Sánchez en otra instancia.
- Pilotos en clientes concretos (SENASA, Team Quality). Quedan para después.
- Relay: que un Alloy de un bastión reciba y reenvíe datos de otros hosts.
  Cada host envía directo, con proxy si hace falta.
- Trazas, APM y profiles.
- Vencimiento de certificados locales: queda como opcional a evaluar más
  adelante (ver "Señales opcionales").

**Anti-objetivos**

- Que una config inválida llegue al servicio en ejecución y deje al host sin
  enviar.
- Que un `apt upgrade` o `dnf upgrade` del cliente cambie la versión de Alloy
  sin que nos enteremos.
- Secretos en texto plano en el repo, en los logs de Ansible o en el archivo de
  config principal.
- Mandar por defecto todo lo que expone node exporter: rompería el free tier.

## Restricciones

- Nunca se ejecuta contra hosts de clientes sin confirmación: primero
  `--check --diff`. El rol tiene que soportar `--check` sin fallar.
- **Repo en GitHub: `Mikroways/ansible-mikroways-alloy`**, público, como el
  resto de los roles `mikroways.*`. Lo decidió Christian: es una excepción a la
  regla de GitLab del proyecto, porque el rol es público y se publica en Galaxy.
  - Como en todo repo de `Mikroways/*`, se trabaja desde un fork en la cuenta
    `apps-mikroways` y el PR se abre desde el fork.
  - Christian crea el repo y Mika lo suma al proyecto. Tiene que tener al menos
    un commit inicial, porque un repo vacío no se puede forkear.
  - Se publica en Galaxy como `mikroways.alloy`
    (`galaxy_info.role_name: alloy`).
- Convenciones de Mikroways para roles (tomadas de `mikroways/ansible/mw-user`,
  `Mikroways/ansible_restic` y otros): namespace Galaxy `mikroways`, Molecule
  con driver Docker, dependencias Python con `uv`, `yamllint` y `ansible-lint`.
- `ansible-core` 2.19 o superior (igual que `mw-user`).
- Los secretos llegan como variables. El rol no decide si vienen de
  ansible-vault o de sops: eso es del playbook que lo usa.

## Enfoques considerados

| | Enfoque | A favor | En contra |
|---|---|---|---|
| **A (elegido)** | Rol propio `mikroways.alloy` | Control total de instalación y config. Windows entra después en el mismo rol. Sin dependencia del ritmo de otra collection. | Mantenemos nosotros las tareas de instalación (pocas por familia de SO). |
| B | `grafana.grafana.alloy` para instalar, con nuestros templates encima | Menos código de instalación. | No soporta Windows, así que igual habría un camino aparte. Recibe la config como un string único. Instala `latest` por defecto. |
| C (descartado) | Fleet Management (`remotecfg`) | Pipelines centralizados. | Ata cada host a un stack de Grafana Cloud y saca la config de git. Choca con el gateway y con "curado y versionado". |

Christian eligió A y pidió **instalar el release desde el GitHub de Grafana**.

## Lo decidido

### Instalación

- **Fuente:** el paquete `.deb` o `.rpm` del release de GitHub
  (`https://github.com/grafana/alloy/releases/download/v<versión>/alloy-<versión>-1.<arch>.{deb,rpm}`).
  El mismo `.deb` sirve para Ubuntu y Debian y el `.rpm` para RHEL-like.
  Verificado en v1.21.1: el release publica paquetes amd64, arm64, ppc64el y
  s390x, y un `SHA256SUMS`.
- **Integridad:** se verifica el sha256 contra el `SHA256SUMS` del mismo
  release. El release no publica firmas GPG de los paquetes. Esto queda
  registrado como riesgo.
- **Versión fijada** en `alloy_version`, sin default `latest`. El rol solo
  descarga e instala cuando la versión instalada es distinta. Permite downgrade.
- **Sin repo de paquetes en el host:** como no se agrega `apt.grafana.com` ni
  `rpm.grafana.com`, una actualización del sistema no toca Alloy. Esto cubre un
  anti-objetivo y es una ventaja de usar GitHub frente a los repos.
- **Alloy ya instalado o repo de Grafana presente** *(decisión mía)*:
  - En Debian/Ubuntu el rol marca el paquete en `hold` (`dpkg_selections`), así
    ni un repo de Grafana ya configurado lo actualiza.
  - En RHEL-like, si encuentra un repo que ofrece `alloy`, avisa con un warning
    y no toca el repo del cliente.
  - Si hay un Alloy instalado de otra fuente, lo reemplaza por la versión
    fijada.
  - Grafana Agent queda fuera: si está, el rol avisa y no lo toca.
- **Mirror propio:** `alloy_download_base_url` permite apuntar a un mirror
  interno (por ejemplo, un proxy de GitHub en Nexus) con la misma estructura de
  rutas. Esto responde a la pregunta del issue: los repos oficiales existen
  (`apt.grafana.com` para Debian y Ubuntu, `rpm.grafana.com` para RHEL-like),
  pero no los usamos.
- **Dónde se descarga:** por defecto en el host, respetando el proxy.
  `alloy_download_on_controller: true` descarga en el controlador y copia el
  paquete, para hosts que no llegan a GitHub ni por proxy.

### Archivos y servicio

- El paquete crea el usuario `alloy`, lo agrega a `adm` y `systemd-journal`, y
  el servicio corre como `alloy`. Se respeta ese esquema: el rol no corre Alloy
  como root.
- El servicio lee `CONFIG_FILE` de `/etc/default/alloy` (Debian/Ubuntu) o de
  `/etc/sysconfig/alloy` (RHEL-like). El rol administra ese archivo y lo apunta
  al directorio `/etc/alloy/conf.d/`. Alloy carga todos los `*.alloy` de un
  directorio, sin subdirectorios. El `config.alloy` de ejemplo del paquete no
  se usa.
- El rol es dueño exclusivo de `conf.d/`: borra los `*.alloy` que no generó, así
  apagar una señal borra su archivo.
- Un archivo por señal: `00-labels-y-envio.alloy`, `10-host.alloy`,
  `20-servicios.alloy`, `30-textfile.alloy` (o dentro de `10-host`, a criterio
  del builder), `40-journal.alloy`, `50-archivos.alloy` y `90-self.alloy`.
  Además, `alloy_extra_config_files` como vía de escape para pipelines propias
  de un cliente.
- **Validación como conjunto:** los archivos se referencian entre sí, así que
  no alcanza con validarlos uno por uno. La config completa pasa por
  `alloy validate <dir>` antes de reemplazar la que usa el servicio. Si no
  valida, el rol falla y el servicio sigue con la config anterior.
- Si cambia la config, el handler hace `reload` (SIGHUP). Si cambia el archivo
  de entorno o el paquete, hace `restart`.
- **Secretos** en archivos aparte en `/etc/alloy/secrets/`, dueño `root:alloy`,
  modo `0640`. La config los referencia con `password_file`,
  `credentials_file` o `client_secret_file`, nunca con el valor en línea. Las
  tareas que los tocan llevan `no_log: true`.
- **`state: absent`:** para y deshabilita el servicio, desinstala el paquete y
  borra `conf.d/`, `secrets/`, el archivo de entorno y `/var/lib/alloy` (WAL).
  El directorio de textfile no se borra si lo comparte con otros (ver
  Textfile). El usuario `alloy` se borra solo si `alloy_remove_user: true`.

### Envío

- Un `prometheus.remote_write` y un `loki.write`, con URL propia cada uno:
  `alloy_metrics_url` y `alloy_logs_url`.
- **Auth**, una para los dos: `alloy_auth_type` acepta `none`, `basic`,
  `bearer`, `header` u `oauth2`.
  - `basic`: usuario y password.
  - `bearer`: token.
  - `header`: nombre y valor (por ejemplo `X-Api-Key`).
  - `oauth2`: `token_url`, `client_id`, `client_secret` y `scopes`.

  Cubre tanto el envío directo a Grafana Cloud (basic, el contrato de
  LABSMW-26) como el gateway (API key u OAuth2 con Keycloak, LABSMW-33).
- **Credenciales por endpoint** *(decisión mía)*: en Grafana Cloud, Prometheus
  y Loki tienen usuarios distintos (cada uno su instance ID) y comparten el
  token. Por eso hay una auth común (`alloy_auth`) y cada endpoint puede pisar
  campos sueltos (`alloy_metrics_auth`, `alloy_logs_auth`, por ejemplo solo el
  `username`). El escenario de Molecule de basic usa usuarios distintos para
  métricas y para logs.
- **Proxy:** `alloy_proxy_url` y `alloy_no_proxy` se aplican a los dos
  endpoints y al `token_url` de OAuth2. El default es sin proxy. Se asume que
  algunos clientes lo necesitan.
- **TLS:** se verifica siempre. CA propia opcional con `alloy_tls_ca_pem` (el
  rol la escribe a un archivo) o `alloy_tls_ca_file`. Existe
  `alloy_tls_insecure_skip_verify`, con default `false`, y el rol avisa con un
  warning si se activa.

### Labels

- `alloy_labels_cliente` y `alloy_labels_entorno` son obligatorias: el rol
  falla con un mensaje claro si faltan.
- `host` toma por defecto `inventory_hostname`.
- `os` vale `linux` (y `windows` más adelante). Es de cardinalidad baja: la
  distro y su versión ya vienen en `node_os_info`.
- `alloy_extra_labels` (dict) agrega labels extra.
- Se aplican como `external_labels` en el envío de métricas y de logs, así no
  se repiten en cada componente.
- **`instance` y `job`** *(decisión mía, a coordinar con LABSMW-32)*:
  - `instance` vale lo mismo que `host`.
  - `job` es fijo por señal: `integrations/node_exporter`,
    `integrations/process_exporter` e `integrations/alloy`. Son los valores que
    esperan los dashboards y alertas de las integraciones de Grafana.

  Si el catálogo de LABSMW-32 pide otra cosa, se cambia en un solo relabel.

### Señales

**Métricas de host** (`prometheus.exporter.unix`)

- `set_collectors` con una lista corta por defecto: `cpu`, `loadavg`,
  `meminfo`, `filesystem`, `diskstats`, `netdev`, `uname`, `os`, `time`,
  `timex`, `boottime`, `textfile` y `systemd` (si hay units vigiladas, que
  incluyen las detectadas de NTP y Teleport).
- Variable `alloy_unix_collectors`.
- Excluye filesystems y dispositivos virtuales con defaults sensatos:
  `fs_types_exclude` y `mount_points_exclude` del default de Alloy; en `netdev`,
  `device_exclude` de `lo`, `veth*`, `docker*`, `br-*` y `cali*`.
- Pasa por un `prometheus.relabel` con allowlist de nombres de métrica
  (`alloy_metrics_allowlist`, regex). Ahí aterriza el catálogo de LABSMW-32.
  Mientras ese catálogo no esté, el default es la lista mínima para CPU, load,
  memoria, disco, filesystem, red y uptime.
- `alloy_scrape_interval`, con default `60s`, para cuidar las DPM del free
  tier.

**Servicios y procesos**

- `alloy_systemd_units`: lista de units. Arma el `unit_include` del collector
  `systemd`. Se guarda solo el estado `active` (las demás series de estado se
  descartan en el relabel) más `node_systemd_service_restart_total` (opción
  `enable_restarts` del collector) si `alloy_systemd_restarts: true`. Con esto alcanza para alertar "no está
  active" sin multiplicar series.
- `alloy_processes`: lista de `{nombre, cmdline_regex}` para procesos que no
  son units, con `prometheus.exporter.process` y métricas recortadas a
  `namedprocess_namegroup_num_procs`.

**Textfile**

- Default: `/var/lib/node_exporter`, el mismo que usa `mikroways.restic`
  (`restic_prometheus_exporter_metrics_basedir`). Así los backups de restic
  publican sin tocar nada.
- El rol crea el directorio si no existe y no lo borra en `absent` si no lo
  creó. Las métricas de textfile pasan por la allowlist con un patrón propio
  (`alloy_textfile_allowlist`, default `restic_.*|kopia_.*|backup_.*`).

**Logs**

- journald con `loki.source.journal`. Se filtra por prioridad con
  `relabel_rules` sobre `__journal_priority`. `alloy_logs_min_priority` va
  por nombre (`warning` por defecto, que mantiene 0 a 4). Como `matches` no
  admite OR, el filtro no se puede hacer ahí.
- Se conservan como labels `unit` y `level`. Nada de PID ni de otros campos de
  alta cardinalidad.
- Archivos: `alloy_log_files`, lista de `{path (glob), labels, level_regex}`.
  Se descartan las líneas que no matchean `level_regex`, con default
  `(?i)\b(warn(ing)?|err(or)?|crit(ical)?|fatal|alert|emerg(ency)?)\b`.
- `max_age` de journal en `12h`: en la primera corrida no se manda todo el
  historial.
- **Permisos de logs de aplicaciones** *(decisión mía)*:
  - El rol no cambia permisos ni ACLs de archivos del cliente.
  - Verifica que el usuario `alloy` pueda leer cada `path` configurado y, si
    no, avisa con un warning que nombra el archivo.
  - `alloy_extra_groups` permite sumar `alloy` a grupos existentes (por ejemplo
    el de la aplicación) cuando el cliente lo autoriza.

**Self-monitoring**

- `prometheus.exporter.self` con allowlist corta (`alloy_build_info` y las
  métricas de envío y errores de `prometheus_remote_storage_*` y
  `loki_write_*`). El metamonitoreo de LABSMW-32 detecta un Alloy que deja de
  enviar por la ausencia de esas series.

**NTP (encendido por defecto)**

Christian lo pidió porque Teleport emite certificados de vida corta y un reloj
corrido deja al bastión sin acceso.

- El collector `timex` aporta `node_timex_sync_status`,
  `node_timex_offset_seconds` y `node_timex_maxerror_seconds`. Lee el estado
  del kernel, así que sirve igual con chrony, timesyncd o ntpd.
- El rol detecta cuál de las tres units está presente (`chrony`/`chronyd`,
  `systemd-timesyncd` o `ntpd`) y la suma sola a la lista de units vigiladas.
- Las alertas (no sincronizado, offset alto) se proponen a LABSMW-32.

**Teleport (automático si el host tiene el agente)**

`alloy_teleport_enabled` vale `auto` por defecto: se prende si existe la unit
`teleport.service`. Las señales son:

- **Estado del servicio:** `teleport.service` se suma a las units vigiladas.
- **Logs:** los warning/error de la unit ya entran por journald, con el label
  `unit`.
- **Métricas y salud del agente** (si `alloy_teleport_diag_addr` está
  definido, por ejemplo `127.0.0.1:3000`):
  - Se scrapea `/metrics` con allowlist corta (`process_state`,
    `teleport_build_info` y el `up` del scrape) y `job="integrations/teleport"`.
  - Si la allowlist se queda corta, se ajusta probando contra un agente real.
  - "El agente está conectado al cluster" sale de `process_state`.
- **Dependencia externa:** hoy `Mikroways/ansible-teleport` deja fijo
  `diag_addr: ""` en `default_teleport.yaml.j2`. Hace falta un PR, desde un
  fork, que lo haga configurable (`teleport_diag_addr`, default `""` para no
  cambiar nada a quien no lo use). Es un cambio aparte de este rol. Mientras
  no esté, Teleport queda cubierto por el estado del servicio, los logs y NTP.

**Señales opcionales (a evaluar, apagadas en v1)**

- Vencimiento de certificados locales: no hay componente nativo simple.
  Queda fuera de la v1.

### Estructura del rol

```text
defaults/main.yml          # todas las variables documentadas
meta/main.yml              # galaxy_info: namespace mikroways, role_name alloy
tasks/main.yml             # assert de variables → include por estado y SO
tasks/linux/install.yml
tasks/linux/configure.yml
tasks/linux/uninstall.yml
tasks/windows/             # vacío en v1, reservado
templates/conf.d/*.alloy.j2
templates/env.j2
handlers/main.yml
molecule/<escenarios>/
```

### Pruebas

- **SO soportados en v1** *(decisión mía)*:
  - Debian 11, 12 y 13.
  - Ubuntu 20.04, 22.04 y 24.04.
  - EL 8, 9 y 10 (RHEL, Rocky, Alma y Oracle Linux).
  - Amazon Linux 2023 como best-effort, sin CI.
  - El rol hace `assert` sobre esa lista.
- **Matriz de Molecule:** imágenes con systemd de Debian 12, Ubuntu 22.04,
  Ubuntu 24.04, Rocky 8 y Rocky 9. Las demás versiones de la lista no entran en
  CI para no alargarlo.
- **Runners:** GitHub Actions (`ubuntu-latest`) con Docker. Si systemd en
  contenedor da problemas con cgroup v2, se usan las opciones de Molecule
  `cgroupns_mode: host` y el volumen `/sys/fs/cgroup` con permiso de
  escritura.
- Receptor local en contenedores en la misma red de Molecule:
  - Prometheus con `--web.enable-remote-write-receiver`.
  - Loki single binary.
  - nginx adelante, que exige la auth del escenario: basic, bearer, header y un
    `token_url` falso que emite un token fijo para OAuth2.
  - tinyproxy para el escenario con proxy, porque es lo que usa el proyecto.
- Escenarios:
  - `default`: basic auth y todas las señales.
  - `auth-header`, `auth-bearer` y `auth-oauth2`.
  - `proxy`: el host no tiene salida directa, solo vía tinyproxy.
  - `teleport`: una unit falsa `teleport.service` que sirve un `/metrics` de
    prueba en el `diag_addr`. Verifica la detección automática, el scrape y la
    allowlist.
  - `absent`: instala, desinstala y verifica que no quede nada.
- `verify`:
  - En Prometheus: `node_load1` y `alloy_build_info` con
    `cliente`/`host`/`entorno`/`os`, el estado de una unit de prueba y una
    métrica de un `.prom` de prueba, `node_timex_sync_status` y el estado de
    la unit de NTP detectada.
  - En Loki: un `logger -p err` llega y un `logger -p info` no.
  - En el escenario de proxy: el log de tinyproxy muestra el tráfico.
- Idempotencia con el paso estándar de Molecule (segunda corrida sin cambios).
  `--check` sobre un host ya convergido no falla.

### CI y versionado

- GitHub Actions, como `mw-user`:
  - `yamllint`, `ansible-lint` y `molecule test` en matriz por escenario, en
    `ubuntu-latest`, con `uv sync`. Esos runners corren contenedores con
    systemd, así que se cae el riesgo de los runners privilegiados de GitLab.
  - Un workflow de publicación en Galaxy al crear un release, que necesita el
    secret `GALAXY_API_KEY` en el repo o en la organización.
- Licencia MIT, igual que `Mikroways/ansible-teleport`.
- Versionado semántico con tags `vX.Y.Z` y CHANGELOG. La versión de Alloy
  fijada por default se actualiza en un MR propio, para que se vea en el
  CHANGELOG.

## Lo que queda al builder

- Los nombres exactos de las variables, siempre con prefijo `alloy_` y
  documentadas en `defaults/main.yml` y en el README.
- Cómo se implementa la validación como conjunto (directorio de staging u otra
  forma), siempre que se cumpla que una config inválida no llega al servicio y
  que la segunda corrida da 0 cambios.
- Cómo se arma el receptor falso y si los contenedores se levantan en
  `prepare` o como plataformas de Molecule.
- La lista exacta de la allowlist inicial, dentro de lo que pide la sección
  Señales.
- La redacción del README, que incluye ejemplos para host Linux, bastión, con
  proxy, con gateway y con Grafana Cloud directo.

## Riesgos

1. **Paquetes de GitHub sin firma GPG:** la integridad depende del
   `SHA256SUMS` servido por HTTPS desde el mismo release. Mitigación: fijar la
   versión y verificar el checksum. Si hace falta más, se puede comparar contra
   la firma del paquete en `rpm.grafana.com` o `apt.grafana.com` en CI al
   subir de versión.
2. **Paquetes de ~170 MB por host:** la descarga en lote puede pesar en enlaces
   lentos o en el proxy del cliente. Mitigación: se descarga solo si cambia la
   versión, y existen `alloy_download_on_controller` y el mirror.
3. **El catálogo de LABSMW-32 todavía no está:** los defaults de allowlist
   pueden cambiar y obligar a una versión menor. Mitigación: allowlist por
   variable y CHANGELOG.
4. **El contrato del gateway (LABSMW-33) todavía no está:** si pide algo que no
   sea basic, bearer, header u OAuth2 client credentials, hay que sumarlo.
   Mitigación: los cinco modos cubren las dos opciones del issue del gateway.
5. **systemd dentro de Docker en CI:** en GitHub Actions funciona con
   `privileged` y cgroupns `host`. Si falla, se cambia a un driver de VM.
6. **SO viejos (EL7, Ubuntu 18.04 o anteriores):** fuera de la v1. El rol
   falla con un mensaje claro en vez de instalar a medias.
7. **Ubuntu 20.04 trae Python 3.8**, que ansible-core 2.20 o superior no
   maneja. El rol lo soporta, pero para esos hosts el playbook tiene que usar
   ansible-core 2.19. Va en el README.

## Pregunta resuelta

Dónde vive el rol: en GitHub, `Mikroways/ansible-mikroways-alloy`, publicado en
Galaxy (ver Restricciones).
