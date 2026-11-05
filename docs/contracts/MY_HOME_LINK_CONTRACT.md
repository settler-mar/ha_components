# MY_HOME Link — универсальный контракт межмодульной связи

`MY_HOME Link` — внутренний интерфейс между producer- и consumer-модулями. Он не знает о платах, Board, MQTT или Home Assistant. Отопление использует его первым профилем.

## Runtime modes

- `disabled` — link не передаёт команды и feedback не считается действительным;
- `physical` — consumer использует реальный feedback;
- `virtual` — тестовый consumer, не имеющий доступа к physical device dispatcher.

После перезапуска runtime mode всегда сбрасывается в `disabled`.

## Systems and bindings

`Home Assistant` and `ESP` are execution systems; `floor_heating` and `boiler_ctrl` are logical modules.

Each value also contains `source`, `target` and `ha_binding`. The binding mode is one of `none`, `virtual_port` or `ha_entity`.

Example endpoint:

```json
{"system": "home_assistant", "module": "floor_heating"}
```

Example real HA entity binding:

```json
{"mode": "ha_entity", "entity_id": "sensor.boiler_supply"}
```

`virtual_port` is for display and testing only and cannot control physical outputs.

## Value contract

Каждое значение описывается полями:

| Поле | Назначение |
|---|---|
| `name` | стабильное имя значения внутри link |
| `direction` | `producer_to_consumer` или `consumer_to_producer` |
| `value_type` | `boolean`, `number`, `integer`, `string`, `json` |
| `unit` | единица измерения или `null` |
| `minimum`, `maximum` | допустимый диапазон |
| `initial` | значение до первого обновления |
| `on_stale` | безопасное значение при stale/timeout |
| `timeout_s` | максимальный возраст значения |
| `error_behavior` | действие при ошибке, по умолчанию `reject` |
| `source` | система и логический модуль, формирующие значение |
| `target` | система и логический модуль, принимающие значение |
| `ha_binding` | интерфейс HA: `none`, `virtual_port` или `ha_entity` |

Runtime state дополнительно содержит `quality`, `updated_at`, `age_s` и `error`.

## Safety rules

- `disabled` не пропускает значения через write endpoint;
- invalid type/range получает `quality=invalid`;
- после половины timeout значение становится `stale`;
- после timeout значение становится `timeout` и заменяется на `on_stale`;
- virtual mode обновляет только тестовое состояние link;
- `physical_outputs_protected=true` является обязательным признаком состояния;
- virtual mode не вызывает `DeviceCommandDispatcher`.

## Первый профиль

Профиль `floor-to-boiler` использует:

- producer: `floor_heating`;
- consumer: `boiler_ctrl`;
- request: `boiler_enable`, `boiler_temperature`, `demand_percent`, `turbo`, `quality`;
- health: `ok`;
- feedback: `ready`, `supply`.

API:

```text
GET  /api/module-links
GET  /api/module-links/{link_id}
PUT  /api/module-links/{link_id}
POST /api/module-links/{link_id}/mode
POST /api/module-links/{link_id}/values/{value_name}
PUT  /api/module-links/{link_id}/values/{value_name}/binding
```

UI может использовать `/api/module-links` как начальный snapshot, а `/ws` — для событий `module_link`.
