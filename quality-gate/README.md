# Portable AI Quality Gate

Orquestador de verificación de calidad pre-producción, portable y agnóstico de agente/stack.
**La IA orquesta, interpreta y explica. Nunca decide el PASS/FAIL** — eso lo hace un motor de
reglas determinista (`config/rules.yml`).

## Quickstart (en el proyecto destino)

```bash
# 1. Copiar el directorio quality-gate/ al proyecto (o el ZIP de dist/)
# 2. Inicializar y descubrir el stack
qg init
qg discover
# 2b. Copiar y ajustar la configuración (obligatorio si quieres las guardas de rama)
cp settings.json.example settings.json
#     → require_branch: ramas autorizadas; require_clean: bloquea cambios sin commitear
#     OJO: settings.json se lee con JSON estricto — si lo copias con comentarios //,
#     el gate se NIEGA a correr (exit INFRA) y avisa por stderr; nunca corre
#     en silencio sin guardas.
# 3. Preparar el entorno (venv de tools + sandbox si hay Dockerfile)
qg setup
# 4. Ejecutar el gate
qg run                # pre_production (completo)
qg run --trigger pre_merge   # ligero (SAST + deps)
qg run-skill sast     # una skill suelta
qg get-report         # veredicto + evidencia
```

## Resolución de la raíz de la app (monorepo)

El gate detecta en qué directorio vive la app que se va a analizar (spec §10.1):

1. **Override** — `project.app_root` en `settings.json` (p. ej. `"backend"`) gana siempre.
2. **Heurística** — si la raíz no es una app, sondea `backend/`, `src/`, `app/`,
   `server/`, `api/` (requieren `pyproject.toml`/`requirements.txt` + `app/main.py`
   o `manage.py`). Un único candidato se usa; **varios candidatos = ambiguo** y el
   gate se detiene pidiendo el override en vez de adivinar.
3. **Raíz** — fallback: la raíz del proyecto.

`qg discover` imprime la raíz resuelta (`app root: backend (heuristic)`); el
veredicto nunca se decide sobre un directorio equivocado en silencio.

## Modelo de aislamiento

| Herramienta | Layer | Aislamiento | Efectos sobre el proyecto analizado |
|---|---|---|---|
| ruff, black, semgrep, pip-audit | venv uv | Blando: proceso aislado, network del host, FS del proyecto en lectura | no escriben nada |
| pytest + coverage | venv uv — deps-venv si `qg setup` lo provisionó (si no, venv del gate) | Blando, única escritura permitida: `COVERAGE_FILE` redirigido a `artifacts/`; pytest corre con `-p no:cacheprovider` (no se crea `.pytest_cache`) | cero rastros |
| trivy, k6, truffleHog | container | Duro: imagen con digest fijo, código montado read-only, red del sandbox | nada |

**Asimetría de aislamiento (v0.1):** la tool layer es híbrida a propósito — los tooling de
Python corren en el venv local (aislamiento blando: comparten kernel y red del host), mientras
que trivy/k6/truffleHog corren en contenedores con digest fijo y código montado read-only
(aislamiento duro). El venv local no aísla red ni kernel; los contenedores sí. El sandbox de
integración (`sandbox/docker-compose.yml`) es la única excepción controlada: red propia
`qg_sandbox` y volúmenes gestionados.

## Atribución y guardas de estado

`qg run` y `qg run-skill` identifican qué estado exacto se va a validar y lo
imprimen como banner **antes** de ejecutar cualquier herramienta:

```
WARNING: analyzing branch 'dev' @ 1a2b3c4 (dirty: uncommitted changes present).
```

La huella viaja también al reporte: `analyzed_state` en `summary.json` y una línea
`**Analyzed:**` en `summary.md`.

Dos guardas de ejecución se configuran en `settings.json` → `project`:

- `require_branch` (lista) — si la rama actual no está listada, el gate **se niega
  a correr** (exit INFRA) antes de que se ejecute cualquier herramienta. Un string
  suelto se normaliza a una lista de un elemento.
- `require_clean` (`true`) — el gate se niega a correr si el working tree tiene
  cambios sin commitear. Solo el booleano literal `true` la activa.

Ambas son **precondiciones de ejecución** (config-driven), nunca métricas de
calidad: no influyen en el veredicto PASS/FAIL, que sigue viviendo en
`config/rules.yml`.

En un directorio sin git el banner advierte que el estado no puede atribuirse a
una rama/commit; las guardas que requieren git (`require_branch` / `require_clean`)
se niegan a correr en ese caso.

## Sandbox de integración (k6)

El override del sandbox — la app analizada montada como servicio `app` de
`sandbox/docker-compose.yml` — se configura en `settings.json` → `project.sandbox`:

- `health_path` — ruta que k6 valida contra `BASE_URL` (default `/health`).
- `env` — objeto de variables inyectadas como `environment` del contenedor `app`.

Si la red `qg_sandbox` no está levantada, la skill de performance se marca
**SKIPPED** (no ERROR), con la pista de arrancar el sandbox: `qg setup` +
`docker compose up -d` en `sandbox/`. La comprobación es de solo lectura, con
timeout de 30s.

## Provisioning del venv

`qg setup` crea un venv dedicado en `artifacts/deps-venv` (con el intérprete del
venv del gate) e instala en él: `pytest` primero, luego las dependencias
declaradas del proyecto analizado (`-r artifacts/project-requirements.txt`, desde
el perfil descubierto) y `coverage`. Así `functional_testing` corre la suite real
con las deps de la app.

El venv del gate (herramientas fijadas: ruff, black, pytest, coverage, semgrep,
pip-audit) **nunca** se toca con los requirements del proyecto.
`functional_testing` usa el binario de `coverage` de `deps-venv` cuando existe
(la instalación de coverage en `deps-venv` es best-effort) y cae al del venv
del gate en caso contrario. Todas las fallas de provisioning del venv son
best-effort (avisos; el setup continúa) — la única que aborta es el
`docker compose up -d` del sandbox, que devuelve exit INFRA.

## Uso para agentes

Lee [AGENTS.md](AGENTS.md): solo comandos `qg <subcomando>` de la whitelist; nunca ejecutes
las herramientas directamente; nunca decidas el veredicto.

## Limitaciones v0.1

- Secrets: solo working tree (sin historial git).
- Performance: k6 smoke + load únicamente.
- Stacks: Python + FastAPI / Django.
- `scheduled_nightly`: diseñado, no implementado.
- trivy: la primera ejecución descarga la base de vulnerabilidades y necesita red; el scan en
  sí corre con `--network none`.
- k6: necesita el sandbox levantado (`qg setup` + `docker compose up -d` en `sandbox/`); si la
  red `qg_sandbox` no está activa, el skill se marca SKIPPED (no produce métricas).
