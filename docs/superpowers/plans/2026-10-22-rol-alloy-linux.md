# Rol mikroways.alloy (v1, Linux): plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development
> (recomendado) o superpowers:executing-plans para implementar este plan tarea
> por tarea. Los pasos usan checkboxes (`- [ ]`) para el seguimiento.

**Objetivo:** un rol de Ansible `mikroways.alloy` que instala Grafana Alloy
desde el release de GitHub en Debian/Ubuntu y RHEL-like y envía por push
métricas de host, NTP, servicios, procesos, textfile, Teleport, logs filtrados y
self-monitoring a un endpoint configurable.

**Arquitectura:**

- Instalación: el rol baja el `.deb` o el `.rpm` del release y verifica su
  sha256 contra `SHA256SUMS`.
- Configuración: genera un archivo `.alloy` por señal en un directorio de
  staging. Cuando ese directorio cambia, valida el conjunto con
  `alloy validate` y recién entonces lo sincroniza a `/etc/alloy/conf.d/`, que
  es lo que lee el servicio.
- Secretos: van en archivos aparte y la config los lee con `local.file`
  (`is_secret = true`).
- Pruebas: Molecule con contenedores con systemd, contra un receptor falso en
  contenedores: Prometheus, Loki, nginx (auth y TLS) y tinyproxy.

**Tech stack:**

- ansible-core 2.19 o superior (con `uv`).
- Molecule y molecule-plugins[docker], con las colecciones `community.docker`,
  `community.general` y `ansible.posix`.
- yamllint y ansible-lint.
- Alloy 1.21.1.
- GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-22-rol-alloy-linux-design.md`

## Restricciones globales

- **Repo y flujo de trabajo:**
  - Repo `Mikroways/ansible-mikroways-alloy`. Se trabaja desde el fork
    `apps-mikroways/ansible-mikroways-alloy`, en la rama `feat/rol-alloy-linux`,
    y el PR se abre desde el fork. Nunca se hace push al repo de la org.
  - Commits con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Metadatos del rol:**
  - Galaxy: `namespace: mikroways`, `role_name: alloy`, licencia MIT,
    `min_ansible_version: "2.19"`.
  - Todas las variables llevan el prefijo `alloy_` y se documentan en
    `defaults/main.yml`.
- **Instalación:**
  - `alloy_version: "1.21.1"`; nunca `latest`.
  - URL del paquete:
    `{{ alloy_download_base_url }}/v{{ alloy_version }}/alloy-{{ alloy_version }}-1.{{ arch }}.{deb|rpm}`,
    con `alloy_download_base_url` en
    `https://github.com/grafana/alloy/releases/download`.
  - Mapeo de arquitectura: `x86_64` → `amd64` y `aarch64` → `arm64`.
- **SO soportados** (con `assert`):
  - Debian 11, 12 y 13.
  - Ubuntu 20.04, 22.04 y 24.04.
  - EL 8, 9 y 10 (RedHat, Rocky, AlmaLinux y OracleLinux).
  - Amazon 2023.
- **Archivos en el host:**
  - Config: `/etc/alloy/conf.d/`. Secretos: `/etc/alloy/secrets/`, dueño
    `root:alloy`, modo `0640`. Staging: `/var/lib/alloy/staging/`.
  - Archivo de entorno: `/etc/default/alloy` (Debian) o `/etc/sysconfig/alloy`
    (RedHat), con `CONFIG_FILE="/etc/alloy/conf.d"`.
- **Comportamiento:**
  - `no_log: true` en toda tarea que toque secretos.
  - Segunda corrida con 0 cambios. `--check` sobre un host convergido no falla.
- **Labels comunes en todas las series y streams:** `cliente`, `host`,
  `entorno` y `os` (`linux`).
  - `instance` vale lo mismo que `host`.
  - `job` por señal: `integrations/node_exporter`,
    `integrations/process_exporter`, `integrations/alloy` e
    `integrations/teleport`.

## Foco de revisión

1. **Host con config previa válida y una variable nueva que la rompe:** el rol
   tiene que fallar en el validate sin tocar `conf.d/`, y el servicio sigue
   enviando. Lo prueba `verify` en el escenario `default` (Tarea 4).
2. **`alloy_metrics_url` vacía con `alloy_state: present`:** tiene que fallar
   con un mensaje claro antes de instalar nada. Lo prueba
   `tests/asserts.yml` (Tarea 1).
3. **Unit listada en `alloy_systemd_units` que no existe en el host:** no tiene
   que romper Alloy; la serie aparece con `active=0` o directamente no
   aparece, y el rol avisa. Lo prueba el escenario `default` (Tarea 6).
4. **Rotación de un secreto (cambia el password y nada más):** Alloy tiene que
   tomar el nuevo valor sin reinstalar, y en el diff de `--check` no puede
   aparecer el secreto. Lo prueba el escenario `default` con un segundo
   converge (Tarea 4).
5. **Versión fijada menor a la instalada (downgrade):** tiene que instalar la
   fijada. Lo prueba el escenario `default` con un `side_effect` (Tarea 3).

---

### Tarea 0: Repo, fork y documentos

**Bloqueada** hasta que exista `Mikroways/ansible-mikroways-alloy` con al
menos un commit.

- [ ] `gh repo fork Mikroways/ansible-mikroways-alloy --clone`. Crear la rama
  `feat/rol-alloy-linux`.
- [ ] Copiar al repo el spec y este plan, en `docs/superpowers/specs/` y
  `docs/superpowers/plans/`.
- [ ] Commit `docs: diseño y plan del rol alloy v1`.

### Tarea 1: Esqueleto, contrato de variables y validaciones

**Archivos:**

- Crear:
  - Metadatos y herramientas: `pyproject.toml`, `uv.lock`, `.yamllint`,
    `.ansible-lint`, `.gitignore`, `LICENSE` (MIT), `meta/main.yml` y
    `meta/requirements.yml` (colecciones).
  - Variables: `defaults/main.yml` y `vars/main.yml`.
  - Tareas: `tasks/main.yml` y `tasks/assert.yml`.
- Test: `tests/asserts.yml` y `tests/inventory`.

**Interfaces que produce:**

- `defaults/main.yml`, con exactamente estas variables:
  - Instalación: `alloy_state` (`present`|`absent`), `alloy_version`,
    `alloy_download_base_url` y `alloy_download_on_controller` (`false`).
  - Envío: `alloy_metrics_url` y `alloy_logs_url` (los dos `""`).
  - Proxy y TLS: `alloy_proxy_url`, `alloy_no_proxy`, `alloy_tls_ca_pem`,
    `alloy_tls_ca_file` y `alloy_tls_insecure_skip_verify` (`false`).
  - Auth:
    - `alloy_auth`: `{type: none, username: "", password: "", token: "",
      header_name: "", header_value: "", oauth2: {token_url: "",
      client_id: "", client_secret: "", scopes: []}}`.
    - `alloy_metrics_auth: {}` y `alloy_logs_auth: {}`.
  - Labels: `alloy_labels_cliente`, `alloy_labels_entorno`,
    `alloy_labels_host` (`"{{ inventory_hostname }}"`) y
    `alloy_extra_labels: {}`.
  - Métricas de host: `alloy_scrape_interval` (`"60s"`),
    `alloy_host_metrics_enabled` (`true`) y `alloy_unix_collectors` (la lista
    del spec, que incluye `timex`).
  - Filtros de métricas: `alloy_netdev_device_exclude`
    (`"^(lo|veth.*|docker.*|br-.*|cali.*)$"`), `alloy_metrics_allowlist`
    (en esta tarea, solo la parte de self-monitoring y `up`; la Tarea 5 suma
    el resto), `alloy_textfile_directory` (`"/var/lib/node_exporter"`) y
    `alloy_textfile_allowlist` (`"restic_.*|kopia_.*|backup_.*"`).
  - Servicios y procesos: `alloy_systemd_units: []`,
    `alloy_systemd_restarts: false`, `alloy_ntp_autodetect: true` y
    `alloy_processes: []`.
  - Teleport: `alloy_teleport_enabled` (`auto`) y `alloy_teleport_diag_addr`
    (`""`).
  - Logs: `alloy_logs_journal_enabled` (`true`), `alloy_logs_min_priority`
    (`warning`), `alloy_logs_journal_max_age` (`"12h"`), `alloy_log_files: []`
    y `alloy_log_files_default_level_regex` (el del spec).
  - Varios: `alloy_self_monitoring_enabled` (`true`),
    `alloy_extra_config_files: []` (`{name, content}`),
    `alloy_extra_groups: []` y `alloy_remove_user: false`.
- `vars/main.yml`:
  - `_alloy_auth_metrics: "{{ alloy_auth | combine(alloy_metrics_auth, recursive=true) }}"`
    y lo mismo para logs.
  - `_alloy_priority_map` (de `emerg: 0` a `debug: 7`).
  - `_alloy_arch_map`.
- `tasks/main.yml`:
  - Incluye `assert.yml`.
  - Si `alloy_state == 'present'`, sigue con `linux/install.yml` →
    `linux/configure.yml`. Si es `'absent'`, con `linux/uninstall.yml`.

- [ ] **Paso 1: test que falla.** `tests/asserts.yml` es un play contra
  `localhost` con `connection: local` y un `block`/`rescue` por caso. Cada caso
  llama a `include_role: {name: alloy, tasks_from: assert}` y en el `rescue`
  hace `assert` de que `ansible_failed_result.msg` contiene el texto esperado:
  - Falta `alloy_labels_cliente` → `"alloy_labels_cliente es obligatoria"`.
  - Falta `alloy_labels_entorno` → `"alloy_labels_entorno es obligatoria"`.
  - `alloy_metrics_url: ""` → `"alloy_metrics_url es obligatoria"`.
  - `alloy_auth.type: foo` → `"alloy_auth.type debe ser uno de none, basic, bearer, header, oauth2"`.
  - `type: basic` sin `password` → `"basic requiere username y password"`.
  - `alloy_logs_min_priority: loud` → `"alloy_logs_min_priority inválida"`.
  - `alloy_version: latest` → `"alloy_version debe ser una versión fija"`.
  - SO no soportado, con un fact falso
    `ansible_facts.distribution: Gentoo` → `"SO no soportado"`.

  Un último caso con todo válido no tiene que fallar.
- [ ] **Paso 2:** `uv run ansible-playbook -i tests/inventory tests/asserts.yml`.
  Esperado: FAIL, porque `tasks/assert.yml` no existe.
- [ ] **Paso 3:** implementar `defaults`, `vars`, `assert.yml` y `main.yml`
  (con `install`, `configure` y `uninstall` vacíos), más `meta/main.yml` con la
  lista de plataformas del spec.
- [ ] **Paso 4:** correr de nuevo el playbook. Esperado: PASS.
  `uv run yamllint . && uv run ansible-lint` sin errores.
- [ ] **Paso 5:** commit `feat: esqueleto del rol y validación de variables`.

### Tarea 2: Receptor falso y escenario `default` (rojo)

**Archivos:**

- Crear:
  - Receptor: `molecule/resources/receiver/nginx.conf`,
    `molecule/resources/receiver/loki.yaml` y
    `molecule/resources/receiver/tinyproxy.conf`.
  - Playbooks compartidos: `molecule/resources/prepare.yml`,
    `molecule/resources/cleanup.yml` y `molecule/resources/verify-tasks.yml`.
  - Escenario: `molecule/default/molecule.yml`,
    `molecule/default/converge.yml` y `molecule/default/verify.yml`.

**Interfaces que produce:**

- Red Docker `alloy-test`, más `alloy-internal` (`internal: true`) para el
  escenario de proxy.
- Contenedores del receptor:
  - `alloy-test-prometheus`: `prom/prometheus` con
    `--web.enable-remote-write-receiver`, publicado en `127.0.0.1:19090`.
  - `alloy-test-loki`: `grafana/loki` single binary, publicado en
    `127.0.0.1:13100`.
  - `alloy-test-receiver`: nginx con alias de red `receiver.test`, TLS en 443
    con un cert firmado por una CA de prueba que `prepare` genera con `openssl`
    en el controlador, en `molecule/resources/receiver/.ca/` (ignorado en git).
  - `alloy-test-proxy`: tinyproxy, en las dos redes.
- Rutas del nginx: `/{basic,bearer,header,oauth2}/api/prom/push`, que van al
  `/api/v1/write` de Prometheus, y `/{...}/loki/api/v1/push`, que van a Loki.
  La auth que exige cada prefijo:
  - `basic`: `metrics-user`/`metrics-pass` para prom y `logs-user`/`logs-pass`
    para loki (htpasswd).
  - `bearer`: `Authorization: Bearer test-token`.
  - `header`: `X-Api-Key: test-key`.
  - `oauth2`: `POST /oauth2/token` devuelve
    `{"access_token":"oauth-token","token_type":"Bearer","expires_in":3600}`,
    y la ruta exige `Bearer oauth-token`.

  Cualquier otra cosa devuelve 401.
- `verify-tasks.yml` corre con `delegate_to: localhost` y recibe:
  - `verify_prom_queries`: lista de `{query, expect: present|absent}`. Hace
    `GET :19090/api/v1/query` con reintentos (30 × 5s) para `present`, y una
    sola consulta, después de los reintentos de las `present`, para `absent`.
  - `verify_loki_queries`: misma lógica, con `query_range` en `:13100` y los
    últimos 10 minutos.
- Plataformas del escenario `default`: `debian12`, `ubuntu2204`,
  `ubuntu2404`, `rockylinux8` y `rockylinux9`. Usan las imágenes
  `geerlingguy/docker-<os>-ansible`, con `privileged: true`,
  `cgroupns_mode: host`, el volumen `/sys/fs/cgroup:/sys/fs/cgroup:rw`,
  `command: ""` y la red `alloy-test`.
- Variables de grupo del escenario: `alloy_labels_cliente: test`,
  `alloy_labels_entorno: ci`,
  `alloy_metrics_url: https://receiver.test/basic/api/prom/push`, la URL de
  logs equivalente, `alloy_auth.type: basic` con `alloy_metrics_auth` y
  `alloy_logs_auth` por usuario, y `alloy_tls_ca_pem` leído del archivo de la
  CA de prueba.

- [ ] **Paso 1:** escribir `verify.yml` del escenario `default` con
  `alloy_build_info{cliente="test",entorno="ci",os="linux",host="<inventory_hostname>",job="integrations/alloy"}`
  como `present`.
- [ ] **Paso 2:** `uv run molecule test -s default --destroy=always`.
  Esperado: FAIL en verify (todavía no se envía nada). Si falla antes, en
  create o prepare, es un bug de esta tarea. Localmente, con podman, exportar
  `DOCKER_HOST=unix:///run/user/$(id -u)/podman/podman.sock`.
- [ ] **Paso 3:** commit `test: receptor falso y escenario default`.

### Tarea 3: Instalación desde el release de GitHub

**Archivos:**

- Crear: `tasks/linux/install.yml`, `tasks/linux/install-Debian.yml`,
  `tasks/linux/install-RedHat.yml`, `templates/env.j2` y `handlers/main.yml`.
- Modificar: `molecule/default/verify.yml` y crear
  `molecule/default/side_effect.yml`.

**Interfaces que produce:**

- Handlers `Restart alloy` y `Reload alloy` (`systemd`, `reloaded`).
- Fact `_alloy_installed_version`, tomado de `package_facts`.

**Comportamiento:**

- **Cuándo descarga:** solo si `_alloy_installed_version != alloy_version`.
- **Descarga:** `get_url` a `/var/cache/alloy/`, con
  `checksum: "sha256:{{ base }}/v{{ v }}/SHA256SUMS"`, y `environment` con
  `https_proxy`/`no_proxy` si `alloy_proxy_url` está definido. Con
  `alloy_download_on_controller`, baja con `delegate_to: localhost`
  (`run_once` por arquitectura) y después copia.
- **Instalación:**
  - Debian: `apt: deb=...`, `allow_downgrade: true` y
    `dpkg_options: force-confdef,force-confold`. Después,
    `dpkg_selections: hold`.
  - RedHat: `dnf: name=<rpm>`, `disable_gpg_check: true` (el release no firma
    los paquetes; la integridad ya la cubre el sha256) y
    `allow_downgrade: true`. Si `dnf repoquery alloy` encuentra un repo,
    `warn`.
- **Servicio:** `env.j2` escribe `CONFIG_FILE`,
  `CUSTOM_ARGS="--server.http.listen-addr=127.0.0.1:12345"` y
  `RESTART_ON_UPGRADE=true`. El servicio queda `enabled`.
- **Usuario:** `user: alloy, groups: alloy_extra_groups, append: true` cuando
  la lista no está vacía.

- [ ] **Paso 1:** agregar a `verify.yml` dos asserts sobre el host: que
  `alloy --version` contiene `v1.21.1` y que `systemctl is-enabled alloy` da
  `enabled`. En `side_effect.yml`, instalar 1.21.0 a mano y volver a converger.
  Después del side effect, la versión instalada vuelve a ser 1.21.1.
- [ ] **Paso 2:** `uv run molecule converge -s default && uv run molecule verify -s default`.
  Esperado: FAIL en los asserts nuevos.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** `molecule converge` dos veces; la segunda con `changed=0`.
  Después, `verify` (los asserts de instalación en PASS; `alloy_build_info`
  sigue en FAIL hasta la Tarea 4).
- [ ] **Paso 5:** commit `feat: instalación de alloy desde el release de GitHub`.

### Tarea 4: Config validada, envío, auth y self-monitoring

**Archivos:**

- Crear:
  - Tareas: `tasks/linux/configure.yml` y `tasks/linux/secrets.yml`.
  - Templates: `templates/conf.d/00-envio.alloy.j2`,
    `templates/conf.d/90-self.alloy.j2` y `templates/macros.j2` (bloques de
    auth, TLS y proxy por endpoint).

**Interfaces que produce:**

- Componentes que consumen las tareas siguientes:
  - `prometheus.relabel "comun"`: pone `instance` igual a `host`, aplica
    `alloy_metrics_allowlist` y reenvía a `prometheus.remote_write "default"`.
  - `loki.write "default"`.
  - Las señales escriben a `prometheus.relabel.comun.receiver` y a
    `loki.write.default.receiver`.
- `external_labels` en los dos writers: `cliente`, `host`, `entorno`, `os` y
  `alloy_extra_labels`.
- Lista `_alloy_conf_files` (nombre → template), a la que cada tarea de señal
  le agrega su archivo.
- Secretos: `local.file "<endpoint>_<campo>" { filename = "/etc/alloy/secrets/<endpoint>_<campo>", is_secret = true }`,
  con `endpoint` ∈ {`metrics`, `logs`} y `campo` ∈ {`password`, `token`,
  `header`, `client_secret`}.
- La auth `header` usa
  `http_headers = { "<name>" = [local.file.<endpoint>_header.content] }`.

**Comportamiento:**

1. Renderiza cada template de `_alloy_conf_files` y cada
   `alloy_extra_config_files` en `/var/lib/alloy/staging/`. Con `find` +
   `file: absent`, borra del staging los `*.alloy` que no estén en la lista.
2. Si algo cambió: corre `alloy validate /var/lib/alloy/staging`. Si falla, el
   rol falla con el stderr y `conf.d/` queda como estaba.
3. Sincroniza staging → `conf.d/` (copy `remote_src` por archivo y borra los
   que sobran), con notify `Reload alloy`.
4. Un cambio en un secreto también notifica `Reload alloy`.
5. `alloy_tls_insecure_skip_verify: true` dispara un `warn`.

Pasos:

- [ ] **Paso 1:** agregar al escenario `default`:
  - En `verify.yml`, `prometheus_remote_storage_samples_total` como `present`.
  - En `side_effect.yml`:
    - Un converge con
      `alloy_extra_config_files: [{name: roto, content: "esto no es alloy"}]`,
      que tiene que fallar (se verifica con `ignore_errors` + `assert`), y
      después comprobar que `conf.d/roto.alloy` no existe.
    - Un converge que cambia `metrics-pass` a `metrics-pass-2`, con el
      htpasswd del receptor actualizado. Después, `verify` sigue en PASS.
- [ ] **Paso 2:** correr `molecule test -s default`. Esperado: FAIL.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** `molecule test -s default`. Esperado: PASS, con idempotencia
  OK. Además, `molecule converge -- --check --diff` en un host convergido: sin
  fallas y sin ningún secreto en la salida (se revisa con `grep metrics-pass`
  en la salida, que tiene que dar 0 coincidencias).
- [ ] **Paso 5:** commit `feat: config validada como conjunto, envío y self-monitoring`.

### Tarea 5: Métricas de host y NTP

**Archivos:**

- Crear: `templates/conf.d/10-host.alloy.j2`.
- Modificar: `defaults/main.yml` (valor de `alloy_metrics_allowlist`),
  `tasks/linux/configure.yml` y `molecule/default/verify.yml`.

**Valores:**

- `alloy_metrics_allowlist` es una regex que se arma con `join` en defaults a
  partir de una lista, para que se pueda leer. Cubre:
  - `up`.
  - Host:
    - CPU, carga y memoria: `node_cpu_seconds_total`,
      `node_load(1|5|15)` y
      `node_memory_(MemTotal|MemAvailable|MemFree|Buffers|Cached|SwapTotal|SwapFree)_bytes`.
    - Filesystem y disco: `node_filesystem_(size|avail|free)_bytes`,
      `node_filesystem_files(_free)?`, `node_filesystem_readonly` y
      `node_disk_(read|written)_bytes_total|node_disk_io_time_seconds_total`.
    - Red: `node_network_(receive|transmit)_(bytes|errs|drop)_total`.
    - Sistema, hora y NTP: `node_uname_info`, `node_os_info`,
      `node_time_seconds`, `node_boot_time_seconds` y
      `node_timex_(sync_status|offset_seconds|maxerror_seconds)`.
  - Servicios, procesos y textfile: `node_systemd_unit_state`,
    `node_systemd_service_restart_total`, `node_textfile_scrape_error` y
    `namedprocess_namegroup_num_procs`.
  - Teleport: `process_state` y `teleport_build_info`.
  - Self-monitoring de Alloy: `alloy_build_info`,
    `prometheus_remote_storage_.*` y `loki_write_.*` (afinar contra el
    `/metrics` real de 1.21.1).
  - Textfile: lo que defina `alloy_textfile_allowlist`.
- Exporter: `prometheus.exporter.unix "host"` con `set_collectors`
  (`alloy_unix_collectors`, más `systemd` si `_alloy_units` no está vacía),
  `netdev { device_exclude }` y `textfile { directory }`.
- Scrape: `prometheus.scrape "host"` con `job_name = "integrations/node_exporter"`
  y `scrape_interval = alloy_scrape_interval`.

Pasos:

- [ ] **Paso 1:** en `verify`, `node_load1{job="integrations/node_exporter",cliente="test"}`
  y `node_timex_sync_status` como `present`; `node_netstat_Tcp_InSegs` y
  `node_cpu_guest_seconds_total` como `absent`.
- [ ] **Paso 2:** correr. Esperado: FAIL.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** correr. Esperado: PASS.
- [ ] **Paso 5:** commit `feat: métricas de host y NTP`.

### Tarea 6: Servicios, procesos, textfile y detección de NTP y Teleport

**Archivos:**

- Crear: `templates/conf.d/20-servicios.alloy.j2` y
  `tasks/linux/detect.yml`.
- Modificar: `tasks/linux/configure.yml`, `molecule/default/prepare.yml` (en
  los hosts: una unit `alloy-test-dummy.service`, que corre `sleep infinity`, y
  el archivo `/var/lib/node_exporter/backup_test.prom`) y
  `molecule/default/verify.yml`.

**Interfaces que produce:**

- `detect.yml` arma `_alloy_units` con `service_facts`: es la unión de
  `alloy_systemd_units`, la primera unit de NTP presente (de
  `chrony.service`, `chronyd.service`, `systemd-timesyncd.service` y
  `ntpd.service`) cuando `alloy_ntp_autodetect`, y `teleport.service` si
  existe y `alloy_teleport_enabled` está en `auto` o `true`.
- `detect.yml` también define `_alloy_teleport_on` (bool).
- Si alguna unit de `alloy_systemd_units` no existe, `warn` con su nombre.

**Comportamiento:**

- **Estado de las units:** `unit_include` es `^(<units escapadas con | >)$`.
  En el relabel de esta señal, `drop` de `node_systemd_unit_state` cuando
  `state != "active"`. `enable_restarts = alloy_systemd_restarts`.
- **Procesos:** si `alloy_processes` no está vacía,
  `prometheus.exporter.process` con un `matcher` por item
  (`name = item.name`, `cmdline = [item.cmdline_regex]`) y
  `job = "integrations/process_exporter"`.
- **Textfile:** el directorio se crea con `0755 root:root` solo si no existe.
  Se registra en `/var/lib/alloy/.textfile-created` que lo creó el rol, para
  que la Tarea 10 sepa si lo puede borrar.

Pasos:

- [ ] **Paso 1:** en `verify`, como `present`:
  - `node_systemd_unit_state{name="alloy-test-dummy.service",state="active"} == 1`.
  - `node_systemd_unit_state{name=~"chronyd?.service|systemd-timesyncd.service"}`
    (en las imágenes que tengan alguna de esas units; si una imagen no la trae,
    `prepare` instala `chrony`).
  - `backup_test_last_success_timestamp_seconds`.
  - `namedprocess_namegroup_num_procs{groupname="sleep"}` (con
    `alloy_processes: [{name: sleep, cmdline_regex: "sleep infinity"}]`).

  Como `absent`: `node_systemd_unit_state{state="inactive"}` y
  `otro_metric_test` (una métrica que `backup_test.prom` también escribe pero
  que no pasa la allowlist).

  Con `alloy_systemd_units` que incluya `no-existe.service`, el converge
  termina bien y emite el warning.
- [ ] **Paso 2:** correr. Esperado: FAIL.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** correr. Esperado: PASS.
- [ ] **Paso 5:** commit `feat: servicios, procesos, textfile y detección de NTP/Teleport`.

### Tarea 7: Logs de journald y de archivos

**Archivos:**

- Crear: `templates/conf.d/40-journal.alloy.j2` y
  `templates/conf.d/50-archivos.alloy.j2`.
- Modificar: `tasks/linux/configure.yml` y los archivos del escenario
  `default`.

**Comportamiento:**

- **journald:** `loki.source.journal` con `max_age`. Las `relabel_rules`
  vienen de un `loki.relabel "journal"` con `forward_to = []` y estas reglas:
  - `keep` de `__journal_priority` con la regex `[0-N]`, donde
    `N = _alloy_priority_map[alloy_logs_min_priority]`.
  - `__journal__systemd_unit` → `unit`.
  - `__journal_priority_keyword` → `level`.

  Etiquetas: `job="integrations/journal"`.
- **Archivos:** si `alloy_log_files` no está vacía, por cada item van
  `local.file_match`, `loki.source.file` y un `loki.process` con
  `stage.match { selector = "{job=\"integrations/logfile\"}" ... }`. Ese
  `stage.match` descarta las líneas que no matchean
  `item.level_regex | default(alloy_log_files_default_level_regex)`; se puede
  implementar con `stage.drop` y `expression` negada o con `stage.regex` +
  `stage.drop`, como resulte más simple. Los labels del item se agregan con
  `stage.static_labels`.
- Si `alloy` no puede leer un `path`, `warn` (se prueba con
  `become_user: alloy` + `test -r`).

Pasos:

- [ ] **Paso 1:**
  - En `prepare`: después del converge, `logger -p user.err "alloy-test-err-<host>"`
    y `logger -p user.info "alloy-test-info-<host>"`, y las líneas
    `"ERROR alloy-file-err"` e `"INFO alloy-file-info"` en
    `/var/log/alloy-test.log` (`0644`). Esto va en `side_effect` o en un paso
    de `verify` antes de las consultas.
  - En `verify`, como `present`:
    `{job="integrations/journal",cliente="test"} |= "alloy-test-err"` y
    `{app="test"} |= "alloy-file-err"`. Como `absent`: `|= "alloy-test-info"`
    y `|= "alloy-file-info"`.
- [ ] **Paso 2:** correr. Esperado: FAIL.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** correr. Esperado: PASS.
- [ ] **Paso 5:** commit `feat: logs de journald y archivos filtrados por nivel`.

### Tarea 8: Escenarios de auth y proxy

**Archivos:**

- Crear: `molecule/auth-bearer/`, `molecule/auth-header/`,
  `molecule/auth-oauth2/` y `molecule/proxy/`. Cada uno tiene `molecule.yml`
  (plataformas `ubuntu2404` y `rockylinux9`, y los playbooks compartidos de
  `molecule/resources/`) y `converge.yml`.
- Modificar: `templates/macros.j2` si hace falta.

**Comportamiento:**

- **Auth:** cada escenario usa el prefijo de nginx que le corresponde y verifica
  `alloy_build_info{host=...}` y un log de journald `present`.
- **Proxy:**
  - Los hosts están solo en `alloy-internal`, y el proxy en las dos redes.
  - `alloy_proxy_url: http://alloy-test-proxy:8888` y
    `alloy_download_on_controller: true`, porque el host no tiene salida.
  - Verifica las mismas series y, además, que el log de tinyproxy (con
    `docker logs`, desde `localhost`) contenga `CONNECT receiver.test:443`.

Pasos:

- [ ] **Paso 1:** escribir los cuatro escenarios con su verify.
- [ ] **Paso 2:** `molecule test -s auth-oauth2` (y los demás). Si alguno
  falla, es por la auth o el proxy y se corrige en `macros.j2`.
- [ ] **Paso 3:** implementar lo que falte.
- [ ] **Paso 4:** los cuatro en PASS.
- [ ] **Paso 5:** commit `test: escenarios de auth y proxy`.

### Tarea 9: Métricas de Teleport

**Archivos:**

- Crear: `templates/conf.d/30-teleport.alloy.j2` y `molecule/teleport/`.
  En ese `prepare`, una unit `teleport.service` falsa que corre
  `python3 -m http.server` sobre un directorio con un archivo `metrics`. Ese
  archivo tiene `process_state 0`, `teleport_build_info{version="17.0.0"} 1` y
  `teleport_otra 1`, y se sirve en `127.0.0.1:3000`.

**Comportamiento:**

- El template se renderiza si `_alloy_teleport_on` y
  `alloy_teleport_diag_addr != ""`.
- `prometheus.scrape "teleport"`: `targets = [{"__address__" = diag_addr}]`,
  `metrics_path = "/metrics"`, `job_name = "integrations/teleport"` y
  `forward_to = [prometheus.relabel.comun.receiver]`.

Pasos:

- [ ] **Paso 1:** en `verify`, como `present`:
  `process_state{job="integrations/teleport"}` y
  `node_systemd_unit_state{name="teleport.service",state="active"}`. Como
  `absent`: `teleport_otra`.
- [ ] **Paso 2:** correr. Esperado: FAIL.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** correr. Esperado: PASS.
- [ ] **Paso 5:** commit `feat: métricas y estado del agente de Teleport`.

### Tarea 10: Desinstalación

**Archivos:**

- Crear: `tasks/linux/uninstall.yml` y `molecule/absent/` (con `converge`
  presente, `side_effect` con `alloy_state: absent` y `verify`).

**Comportamiento:**

- Para y deshabilita el servicio y quita el `hold` (Debian).
- Desinstala el paquete y borra `/etc/alloy/conf.d`, `/etc/alloy/secrets`, el
  archivo de entorno, `/var/lib/alloy` y `/var/cache/alloy`.
- Borra `alloy_textfile_directory` solo si existe
  `/var/lib/alloy/.textfile-created`. Por eso esa marca se lee antes de borrar
  `/var/lib/alloy`.
- Borra el usuario y el grupo `alloy` si `alloy_remove_user`.

Pasos:

- [ ] **Paso 1:** en `verify`, después del side effect, comprobar que no existe
  el paquete (`package_facts`), que no existen los paths de arriba y que
  `systemctl status alloy` termina con código ≠ 0. Un segundo `absent` da
  `changed=0`.
- [ ] **Paso 2:** correr. Esperado: FAIL.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** correr. Esperado: PASS.
- [ ] **Paso 5:** commit `feat: desinstalación limpia con alloy_state absent`.

### Tarea 11: CI, publicación, README y release

**Archivos:**

- Crear: `.github/workflows/test.yml`, `.github/workflows/galaxy.yml`,
  `README.md`, `CHANGELOG.md` y `.github/dependabot.yml` (actions).

**Comportamiento:**

- **`test.yml`:**
  - Corre en PR a `main` y en push a `main`.
  - Un job `lint` (`uv sync`, `yamllint .` y `ansible-lint`).
  - Un job `molecule` en matriz por escenario (`default`, `auth-bearer`,
    `auth-header`, `auth-oauth2`, `proxy`, `teleport` y `absent`), con
    `uv run molecule test -s ${{ matrix.scenario }}`.
  - Un job `asserts` que corre `tests/asserts.yml`.
- **`galaxy.yml`:** el mismo flujo que `Mikroways/mw-user`, `on: release`, con
  el secret `GALAXY_API_KEY`.
- **README** (en español):
  - Qué hace y la tabla de variables.
  - Ejemplos: host Linux con gateway (header u OAuth2), bastión con Teleport y
    NTP, cliente con proxy y mirror, y envío directo a Grafana Cloud (basic con
    usuarios distintos por endpoint; las claves del contrato de LABSMW-26 se
    mapean a `alloy_*`).
  - Una sección "Antes de aplicar en un cliente", con `--check --diff`, que
    explica que primero se muestra el diff.
  - La nota sobre Ubuntu 20.04 y ansible-core 2.19.
- **CHANGELOG:** `## [0.1.0]` con lo que entra.

Pasos:

- [ ] **Paso 1:** push de la rama al fork. El workflow corre en el PR.
- [ ] **Paso 2:** abrir el PR con
  `gh pr create --repo Mikroways/ansible-mikroways-alloy --head apps-mikroways:feat/rol-alloy-linux`.
  En el cuerpo: qué hace, cómo se verificó localmente (los escenarios y su
  resultado) y los riesgos.
- [ ] **Paso 3:** commit `ci: tests en GitHub Actions y publicación en Galaxy` +
  `docs: README y CHANGELOG`.

### Tarea 12 (repo aparte): `teleport_diag_addr` en `Mikroways/ansible-teleport`

- [ ] Hacer el fork y crear la rama `feat/diag-addr-configurable`.
  - En `defaults/main.yml`, agregar `teleport_diag_addr: ""`.
  - En `default_teleport.yaml.j2`, reemplazar el fijo por
    `diag_addr: "{{ teleport_diag_addr }}"`.
  - Agregar a Molecule un caso con `127.0.0.1:3000`.
- [ ] Abrir el PR desde el fork. Con default `""`, no cambia nada para quien no
  la defina.
