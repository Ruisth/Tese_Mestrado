# CONTRACTS.md — Interfaces normativas internas do EGW (v1.0, 07/08/2026)

> Derivado do plano integrado §5 (normativo). Qualquer alteração aqui exige
> atualização coordenada de simulador, controlador, schemas, TDs, deployment,
> harness e testes, e uma entrada no LOG.

## 1. MQTT

| Item | Valor |
|---|---|
| Porta | `8883` (TLS) |
| QoS | 1 |
| Autenticação | username/password (Mosquitto `password_file`) + TLS server-auth |
| Tópico de telemetria | `c2dt/{egw_id}/{device_uuid}/telemetry` |
| Filtro do controlador | `c2dt/+/+/telemetry` |
| Acesso anónimo | proibido |
| Dev/testes locais | perfil `--no-tls` permitido apenas em `localhost` e nunca em benchmarks |

Utilizadores dev (gerados por script, nunca commitados): `egw-controller`,
`egw-simulator`. ACL: simulador só publica em `c2dt/#`; controlador só subscreve.

## 2. Envelope comum de evento (schema_version 1.0.0)

Todos os payloads de telemetria incluem (ver `schemas/telemetry-envelope-v1.schema.json`):

| Campo | Tipo/regra |
|---|---|
| `schema_version` | string semver, `1.0.0` |
| `run_id` | string `[A-Za-z0-9._-]{1,64}`, imutável por execução |
| `message_id` | UUID v5 (namespace abaixo) derivado de `run_id`, `device_uuid`, `seq` |
| `seq` | inteiro ≥ 0, monotónico crescente por dispositivo |
| `ts` | RFC 3339 UTC com sufixo `Z`, resolução ms |
| `egw_id` | string `[A-Za-z0-9._-]{1,64}` |
| `device_uuid` | UUID v4 estável do dispositivo |
| `device_type` | `smartwatch` \| `smart_ring` \| `smart_clothing` |

**Namespace UUID v5:** `6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0` (constante do projeto,
`egw_simulator.envelope.EGW_UUID_NAMESPACE`). Nome: `"{run_id}:{device_uuid}:{seq}"`.

## 3. Medições por dispositivo (campos no nível de topo, junto ao envelope)

| device_type | Taxa nominal | Campos | Gamas |
|---|---:|---|---|
| `smartwatch` | 1,0 msg/s | `heart_rate_bpm` int; `lat`, `lon` number | 25–250; −90..90; −180..180 |
| `smart_ring` | 0,2 msg/s | `skin_temp_c` number; `spo2_pct` int | 30,0–43,0; 50–100 |
| `smart_clothing` | 10,0 msg/s | `accel_x/y/z` number (m/s²); `breathing_rpm` number | −78..78; 4–60 |

Repartição do `--rate` agregado: proporção fixa `1 : 0,2 : 10` (plano §5.6).
Ex.: `--rate 11.2` → smartwatch 1,0 + ring 0,2 + clothing 10,0.

Schemas: `schemas/smartwatch-v1.schema.json`, `schemas/smart-ring-v1.schema.json`,
`schemas/smart-clothing-v1.schema.json` (draft 2020-12, `unevaluatedProperties: false`).

## 4. Gémeos Ditto

| Item | Valor |
|---|---|
| `thingId` | `org.c2dta:{device_uuid}` |
| `policyId` | `org.c2dta:{device_uuid}` (política própria por twin) |
| Atributos | `device_type`, `egw_id`, `schema_version` |
| Sujeito autorizado | `pre:egw-controller` (pre-authentication do gateway Ditto; READ+WRITE em `thing:/` e `policy:/`) |

Features por tipo:

| device_type | Features → propriedades |
|---|---|
| `smartwatch` | `vitals` → `heart_rate_bpm`; `location` → `lat`, `lon` |
| `smart_ring` | `thermo` → `skin_temp_c`; `oximetry` → `spo2_pct` |
| `smart_clothing` | `motion` → `accel_x`, `accel_y`, `accel_z`; `respiration` → `breathing_rpm` |
| todos | `ingestion` → `last_message_id`, `last_seq`, `last_ts`, `accepted_count` |

Idempotência (plano §5.4): rejeitar `message_id` repetido e `seq` ≤ `last_seq`
conhecido. O estado (`ingestion`) vive no twin para sobreviver a restarts do
controlador; cache local é reconstruída lendo o twin no primeiro evento de cada
dispositivo após arranque.

## 5. Controlador (bridge MQTT→Ditto)

- Subscrição assíncrona MQTT (QoS 1); validação JSON Schema **antes** de qualquer
  chamada ao Ditto; conversão para merge-patch e `PATCH /api/2/things/{thingId}`
  (`content-type: application/merge-patch+json`); criação de policy+thing no
  primeiro evento de um `device_uuid`.
- Retry limitado (default 3 tentativas, backoff exponencial 200 ms base) apenas
  para erros transitórios (timeout, 5xx, ligação); 4xx não é retryable.
- Logging estruturado JSON em stderr; contadores: `accepted`, `rejected`,
  `duplicate`, `failed`.
- Endpoints HTTP (porta `8000`):
  - `GET /health` → `{"status":"ok"}` (processo vivo);
  - `GET /ready` → 200 só com MQTT ligado e Ditto acessível; 503 caso contrário;
  - `GET /twins/{device_id}` → leitura do twin normalizada;
  - `GET /metrics` → contadores + uptime (JSON).

### Registo de eventos (fonte primária de latência — plano §5.8/§7.3)

O controlador escreve `events.jsonl` (um por `run_id`, em `EGW_EVENT_LOG_DIR`):

```json
{"run_id":"...","message_id":"...","device_uuid":"...","device_type":"...",
 "seq":0,"received_monotonic_ns":0,"ditto_ack_monotonic_ns":0,
 "latency_ms":0.0,"outcome":"accepted|rejected|duplicate|failed",
 "attempts":1,"error":null}
```

- `received_monotonic_ns`: `time.monotonic_ns()` no callback MQTT;
- `ditto_ack_monotonic_ns`: após resposta 2xx do Ditto;
- `latency_ms = (ditto_ack - received)/1e6`, calculada no mesmo processo;
- `rejected`/`duplicate`/`failed` têm `ditto_ack_monotonic_ns` e `latency_ms` a `null`.

## 6. Variáveis de ambiente (prefixo `EGW_`)

| Variável | Default | Uso |
|---|---|---|
| `EGW_ID` | `egw-01` | identificador do gateway |
| `EGW_MQTT_HOST` / `EGW_MQTT_PORT` | `localhost` / `8883` | broker |
| `EGW_MQTT_USERNAME` / `EGW_MQTT_PASSWORD` | — | credenciais |
| `EGW_MQTT_TLS` | `true` | `false` só para dev local |
| `EGW_MQTT_CA_CERT` | — | caminho do CA para TLS |
| `EGW_MQTT_TOPIC_FILTER` | `c2dt/+/+/telemetry` | subscrição |
| `EGW_DITTO_BASE_URL` | `http://ditto-gateway:8080` | API Ditto |
| `EGW_DITTO_AUTH_MODE` | `pre` | `pre` (header) ou `basic` |
| `EGW_DITTO_PREAUTH_SUBJECT` | `pre:egw-controller` | sujeito pre-auth |
| `EGW_DITTO_USERNAME` / `EGW_DITTO_PASSWORD` | — | se `basic` |
| `EGW_SCHEMA_DIR` | `src/schemas` | diretório dos JSON Schemas |
| `EGW_EVENT_LOG_DIR` | `./data/events` | onde escrever `events.jsonl` |
| `EGW_HTTP_PORT` | `8000` | API do controlador |
| `EGW_RETRY_MAX` | `3` | tentativas Ditto |
| `EGW_RETRY_BACKOFF_MS` | `200` | base do backoff exponencial |

## 7. Simulador — CLI de referência (plano §5.6)

```text
python -m egw_simulator run --scenario nominal --seed 42 \
  --broker <host> --port 8883 --duration 600 --rate 11.2 --output <dir> \
  [--devices smartwatch,smart_ring,smart_clothing] [--egw-id egw-01] \
  [--run-id <id>] [--username u --password p --ca-cert ca.crt | --no-tls] [--qos 1]
```

- Cenários: `smoke`, `nominal`, `load-sweep`, `dropout-reconnect`,
  `invalid-payload`, `soak`.
- Determinismo: mesma seed ⇒ mesma sequência de payloads (por dispositivo).
- Validação local de cada payload antes de publicar, exceto os eventos
  intencionalmente inválidos de `invalid-payload`, que são marcados no registo
  do simulador (`intended_invalid: true`), nunca no payload.
- Output por execução: `manifest.json` (cenário, seed, commit, config, timestamps,
  versão de protocolo) + `sent_events.jsonl`
  (`{run_id, message_id, device_uuid, seq, publish_monotonic_ns, puback_monotonic_ns, intended_invalid}`).

## 8. Portas e serviços (deployment)

| Serviço | Imagem (fixada por digest em `images.lock.env`) | Porta |
|---|---|---|
| Mosquitto | `eclipse-mosquitto:2.x` | 8883 (externa) |
| Ditto gateway | `eclipse/ditto-gateway:3.9.4` | 8080 (rede interna; localhost only no host) |
| Ditto policies | `eclipse/ditto-policies:3.9.4` | interna |
| Ditto things | `eclipse/ditto-things:3.9.4` | interna |
| MongoDB | `mongo:7.x` | interna |
| Controlador | build local (`src/Dockerfile`), `linux/arm64` | 8000 (localhost only) |

`search`, `connectivity` e UI do Ditto ficam fora do core (plano §4.3). Todas as
imagens têm de ser `linux/arm64` verificadas e fixadas por digest.

## 9. Métricas e definições estatísticas (plano §7.3)

`enviada` = entregue ao publish MQTT; `recebida` = callback do controlador;
`duplicada` = `message_id` já processado; `rejeitada` = falha de validação;
`confirmada` = 2xx do Ditto; `perdida` = válida enviada sem confirmação única até
60 s após o fim da execução. Taxa de entrega = confirmações únicas / válidas
enviadas. Unidade estatística = execução, nunca mensagem. Latência primária =
`latency_ms` do controlador (p50/p95/p99).
