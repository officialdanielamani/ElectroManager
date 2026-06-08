# ElectroManager — API Reference

ElectroManager has two distinct API layers:

| Layer | Auth | Who uses it |
|-------|------|------------|
| **External API v1** — `/api/v1/` | `Authorization: Bearer <api_key>` | ESP32, third-party apps, scripts |
| **Internal API** — `/api/`, `/in-out/`, etc. | Session cookie (`@login_required`) | Browser UI only — not for external use |

---

## External API v1

### Authentication

Every request must include the user's personal API key as a Bearer token:

```
Authorization: Bearer <api_key>
```

The API key is tied to a specific user account. All operations performed through the API are recorded under that user.

Keys are stored as SHA-256 hashes on the server — the plain-text key is shown only once at generation time and cannot be recovered. If a key is lost, revoke it and generate a new one.

---

### CORS

All `/api/v1/` endpoints include CORS headers on every response:

```
Access-Control-Allow-Origin:  *
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Max-Age:       86400
```

`OPTIONS` preflight requests are handled automatically. This means browser-based clients running on a different origin — such as a web UI served directly from an ESP32 — can call the API without a proxy.

> **Note:** The `Authorization` header is a non-simple header and always triggers an `OPTIONS` preflight. The preflight is handled by the server; no special client-side configuration is required.

---

### User, Roles & Permissions

The external API fully respects the same RBAC system as the web UI. Access is controlled at three levels:

```
System-wide toggle (admin)
    └── User scope toggle (per-user in Settings → User API)
            └── Role permission (role assigned to the user)
```

**Level 1 — System-wide (Admin controls, Settings → System)**

| Setting | Controls |
|---------|---------|
| `api_item_search_enabled` | Enables/disables Item Search scope for everyone |
| `api_lending_return_enabled` | Enables/disables Lending & Return scope for everyone |
| `api_rack_drawer_enabled` | Enables/disables Location, Rack & Drawer scope for everyone |

If a scope is disabled system-wide, **no user** can use it regardless of their personal settings.

**Level 2 — Per-user (Settings → User API)**

Each user independently enables the scopes they need:

| User field | Scope |
|------------|-------|
| `api_item_search` | Item Search & Information |
| `api_lending_return` | Lending & Return |
| `api_rack_drawer` | Location, Rack & Drawer |

Both Level 1 and Level 2 must be enabled for a scope to work.

**Level 3 — Role permission**

Even with the API enabled and scopes on, the user's role still applies:

| Role permission | Required for |
|-----------------|-------------|
| `lending_return → edit_lending` | Lend and return any contact |
| `lending_return → only_self_lending` | Lend and return to self only |

> The external API always lends to the API key owner — the borrower is always the account that owns the key. There is no way to lend on behalf of another user via the API. This means `only_self_lending` and `edit_lending` roles behave identically for API calls.

**Role access to API settings**

The `users_api → view` and `users_api → run` permissions control whether a user can see and configure their own API settings page (`Settings → User API`).

---

### Rate Limiting

Requests are limited per API key using a sliding 1-second window.

The default limit is **5 requests/second**. Admins can change this in **Settings → System → Server API** (1–100 req/s).

When the limit is exceeded the server returns **429** with a `Retry-After: 1` header.

---

### Error Response Format

All errors follow this shape:

```json
{
  "success": false,
  "code":    "ERROR_CODE",
  "message": "Human-readable description"
}
```

For cart operations that fail per-item, the top-level code is `CART_VALIDATION_FAILED` and per-item detail is in the `items` array (see endpoint docs below).

#### Error codes

| Code | HTTP | Meaning |
|------|------|---------|
| `INVALID_KEY` | 401 | API key missing, empty, or not found |
| `USER_DISABLED` | 403 | User account is inactive |
| `SCOPE_DISABLED` | 403 | Scope is disabled system-wide by admin |
| `NO_PERMISSION` | 403 | User role doesn't allow this operation, or user scope not enabled |
| `ITEM_NOT_FOUND` | 404 | No item matches the given batch_id or ISN |
| `SESSION_NOT_FOUND` | 404 | Lending session ID not found |
| `NO_LENDING_RECORD` | 404 | Item is not currently lent out |
| `RETURN_NO_RECORD` | 404 | Item is lent out but not to this user's account |
| `INVALID_QUERY` | 400 | Query string is missing or empty |
| `BATCH_REQUIRES_ISN` | 400 | Batch uses SN tracking — must look up by ISN, not batch UID |
| `DUE_DATE_PAST` | 400 | `due_date` is in the past |
| `CART_EMPTY` | 400 | `items` array is missing or empty |
| `ITEM_DISABLED` | 403 | Batch is marked as lending-disabled |
| `ISN_IN_USE` | 409 | Serial number is already lent out |
| `NO_STOCK` | 409 | Requested qty exceeds available stock |
| `RETURN_QTY_EXCEEDED` | 400 | Return qty exceeds the user's currently borrowed qty |
| `CART_VALIDATION_FAILED` | 409 | One or more cart items failed — nothing was committed |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `RACK_NOT_FOUND` | 404 | No rack with that UUID |
| `LOCATION_NOT_FOUND` | 404 | No general location with that UUID |
| `MISSING_QUERY` | 400 | `q` parameter is empty |
| `INVALID_POSITION` | 400 | Row/col out of bounds (must be 1-based) |

---

### Timestamps

All timestamps in requests and responses use **ISO 8601** format without timezone offset (server local time):

```
2025-05-21T10:32:00
```

The server always stamps `lend_start` and `return_datetime` — the client only provides `due_date` for lending.

---

### Endpoints

#### `GET /api/v1/lookup`

Validate a batch UID or ISN before adding it to a local cart. Use this during scanning so you can show the user item details and availability before submitting.

**Scope required:** `item_search`

**Query parameter:** `q` — a batch UID (`ABC123DEFG012345-B01`) or ISN (`ISN-0042`)

The server auto-detects the format: it tries ISN first, then batch UID.

**Response — ISN hit:**

```json
{
  "success": true,
  "type": "isn",
  "isn": "ISN-0042",
  "batch_uid": "ABC123DEFG012345-B01",
  "item_name": "Raspberry Pi 4",
  "short_info": "4GB RAM variant",
  "available_for_lending": true,
  "currently_lent": false
}
```

**Response — batch UID hit:**

```json
{
  "success": true,
  "type": "batch",
  "batch_uid": "ABC123DEFG012345-B01",
  "item_name": "Arduino Uno",
  "short_info": "Rev3",
  "available_for_lending": true,
  "available_qty": 8,
  "total_qty": 10
}
```

**Error — batch UID given for an SN-tracked batch:**

```json
{
  "success": false,
  "code": "BATCH_REQUIRES_ISN",
  "message": "This batch uses serial number tracking — search by ISN instead"
}
```

---

#### `GET /api/v1/session/<session_id>`

Look up a past lending or return session by its session ID.

**Scope required:** `lending_return`

Only sessions created by the API key owner are accessible.

**Response:**

```json
{
  "success": true,
  "session_id": "20250521-AB1234",
  "mode": "lend",
  "created_at": "2025-05-21T10:32:00",
  "lend_start": "2025-05-21T10:32:00",
  "due_date": "2025-12-31T23:59:59",
  "notes": "FYP Lab",
  "items": [
    {
      "type": "batch",
      "batch_uid": "ABC123DEFG012345-B01",
      "item_name": "Arduino Uno",
      "qty": 2,
      "returned": false,
      "returned_at": null
    },
    {
      "type": "isn",
      "isn": "ISN-0042",
      "item_name": "Raspberry Pi 4",
      "batch_uid": "XYZ789ABCD012345-B01",
      "returned": false,
      "returned_at": null
    }
  ]
}
```

---

#### `POST /api/v1/lend`

Submit a lending cart. Works identically for one item or many — always send an `items` array.

**Scope required:** `lending_return`

**Role required:** `lending_return → edit_lending` or `lending_return → only_self_lending`

**Request body:**

```json
{
  "items": [
    { "batch_id": "ABC123DEFG012345-B01", "qty": 2 },
    { "batch_id": "XYZ789ABCD012345-B02", "qty": 1 },
    { "isn": "ISN-0042" }
  ],
  "due_date": "2025-12-31T23:59:59",
  "note": "FYP Lab",
  "notify": true,
  "notify_days_before": 3,
  "dry_run": false
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `items` | array | yes | — | At least one entry |
| `items[].batch_id` | string | * | — | Batch UID for normal batches |
| `items[].isn` | string | * | — | ISN for SN-tracked batches |
| `items[].qty` | integer | no | `1` | Normal batches only; ignored for ISN items |
| `due_date` | string | no | `null` | ISO 8601; must be in the future if provided |
| `note` | string | no | `""` | Applied to all items in this session (max 256 chars) |
| `notify` | boolean | no | `false` | Send a reminder notification before `due_date` |
| `notify_days_before` | integer | no | `3` | How many days before `due_date` to notify (1–365) |
| `dry_run` | boolean | no | `false` | Validate without committing — nothing is written |

*Each item needs either `batch_id` or `isn`.

**Success response:**

```json
{
  "success": true,
  "session_id": "20250521-AB1234",
  "lend_start": "2025-05-21T10:32:00",
  "due_date": "2025-12-31T23:59:59",
  "items": [
    { "index": 0, "query": "ABC123DEFG012345-B01", "type": "batch", "item_name": "Arduino Uno",   "batch_uid": "ABC123DEFG012345-B01", "qty": 2, "status": "lent" },
    { "index": 1, "query": "XYZ789ABCD012345-B02", "type": "batch", "item_name": "Breadboard",    "batch_uid": "XYZ789ABCD012345-B02", "qty": 1, "status": "lent" },
    { "index": 2, "query": "ISN-0042",             "type": "isn",   "item_name": "Raspberry Pi 4","batch_uid": "XYZ789ABCD012345-B01",        "status": "lent" }
  ]
}
```

**Validation failure (all-or-none — nothing committed):**

```json
{
  "success": false,
  "code": "CART_VALIDATION_FAILED",
  "message": "One or more items could not be processed. No changes were made.",
  "items": [
    { "index": 0, "query": "ABC123DEFG012345-B01", "status": "ok" },
    { "index": 1, "query": "XYZ789ABCD012345-B02", "status": "error", "code": "NO_STOCK",   "message": "Requested qty 1 exceeds available 0" },
    { "index": 2, "query": "ISN-0042",             "status": "error", "code": "ISN_IN_USE", "message": "ISN-0042 is already lent out" }
  ]
}
```

**Dry-run response (dry_run=true, validation passed):**

```json
{
  "success": true,
  "dry_run": true,
  "message": "Validation passed. No changes made (dry_run=true).",
  "items": [
    { "index": 0, "query": "ABC123DEFG012345-B01", "type": "batch", "item_name": "Arduino Uno", "qty": 2, "status": "ok" }
  ]
}
```

---

#### `POST /api/v1/return`

Submit a return cart. Same array-based approach as lending.

**Scope required:** `lending_return`

**Role required:** `lending_return → edit_lending` or `lending_return → only_self_lending`

The server only allows returning items that are recorded as lent to the API key owner's account.

**Request body:**

```json
{
  "items": [
    { "batch_id": "ABC123DEFG012345-B01", "qty": 1 },
    { "isn": "ISN-0042" }
  ],
  "note": "Returned in good condition",
  "dry_run": false
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `items` | array | yes | — | At least one entry |
| `items[].batch_id` | string | * | — | Batch UID |
| `items[].isn` | string | * | — | ISN |
| `items[].qty` | integer | no | `1` | Normal batches only; must not exceed borrowed qty |
| `note` | string | no | `""` | Applied to all returned items (max 256 chars) |
| `dry_run` | boolean | no | `false` | Validate without committing |

**Normal batch return — FIFO rule:** If a user has borrowed the same batch in multiple separate lending sessions, the oldest active lending record is consumed first. The `qty` field spans across records automatically.

**Success response:**

```json
{
  "success": true,
  "session_id": "20250521-CD5678",
  "status": "on_time",
  "return_datetime": "2025-05-21T14:00:00",
  "items": [
    { "index": 0, "query": "ABC123DEFG012345-B01", "type": "batch", "item_name": "Arduino Uno",   "qty": 1, "on_time": true, "status": "returned" },
    { "index": 1, "query": "ISN-0042",             "type": "isn",   "item_name": "Raspberry Pi 4",          "on_time": true, "status": "returned" }
  ]
}
```

`status` is `"on_time"` if all items were returned before their due date, `"late"` otherwise.

---

### Location, Rack & Drawer

#### `GET /api/v1/location/search`

**Scope required:** `rack_drawer`

Search for items by name, UUID, batch UID, or ISN and return their physical storage locations.

**Query parameters:**

| Parameter | Required | Default | Notes |
|-----------|----------|---------|-------|
| `q` | yes | — | Item name (partial), item UUID, batch UID (`XXXXXXXX-B01`), or ISN |
| `limit` | no | `20` | Maximum results for name searches (max 50) |

The server auto-detects the query type:

| Detected type | `query_type` |
|---|---|
| ISN exact match | `isn` |
| Batch UID pattern (`XXXX-B##`) | `batch_uid` |
| Item UUID (10–20 alphanum chars) | `uuid` |
| Anything else | `name` (partial match) |

**Response:**

```json
{
  "success": true,
  "query": "Arduino",
  "query_type": "name",
  "count": 2,
  "results": [
    {
      "name": "Arduino Mega",
      "item_uuid": "ABC123DEFG012345",
      "sku": "ARD-MEGA",
      "short_info": "2560 variant",
      "locations": [
        {
          "batch_uid": "ABC123DEFG012345-B01",
          "batch_label": "Batch 1",
          "quantity": 10,
          "available": 8,
          "sn_tracking": false,
          "location_type": "rack",
          "rack_uuid": "RACK-UUID-HERE",
          "rack_name": "Main Cabinet",
          "rack_color": "#3a86ff",
          "drawer_cell": "R2-C3",
          "drawer_row": 2,
          "drawer_col": 3,
          "drawer_short_info": "MCU row"
        }
      ]
    }
  ]
}
```

For ISN results an extra `isn` and `lent_out` field appear at the top level of the result entry.

`location_type` can be `rack`, `location`, or `unspecified`.

---

#### `GET /api/v1/location/<location_uuid>`

**Scope required:** `rack_drawer`

Returns metadata for a general location (not a rack), the racks physically placed there, and any items/batches stored directly at that location (i.e. not inside a rack).

**Response:**

```json
{
  "success": true,
  "location": {
    "uuid":        "ABCDE12345L",
    "name":        "Lab A",
    "short_info":  "Main electronics lab",
    "description": "Second floor, room 204",
    "color":       "#28a745"
  },
  "rack_count": 2,
  "item_count": 3,
  "racks": [
    {
      "uuid":       "RACK-UUID",
      "name":       "Main Cabinet",
      "short_info": "Left wall",
      "color":      "#3a86ff",
      "rows":       5,
      "cols":       5,
      "stats": {
        "total_cells": 25,
        "unavailable": 2,
        "used":        8,
        "empty":       15
      }
    }
  ],
  "items": [
    {
      "type":       "item_main",
      "name":       "Oscilloscope",
      "item_uuid":  "XYZ789ABCDEF0123",
      "sku":        "OSC-200",
      "short_info": "200 MHz",
      "quantity":   1,
      "available":  1
    },
    {
      "type":        "batch_override",
      "name":        "Breadboard Kit",
      "item_uuid":   "ABC123DEFG012345",
      "sku":         "BB-KIT",
      "short_info":  "",
      "batch_uid":   "ABC123DEFG012345-B02",
      "batch_label": "Batch 2",
      "quantity":    10,
      "available":   10,
      "sn_tracking": false
    }
  ]
}
```

`items` contains entries stored directly at this location (no rack assigned). `type` is `item_main` (item's primary location is here) or `batch_override` (batch has its own location pointing here). Items inside racks at this location are not included — fetch rack data via `GET /api/v1/rack/<uuid>` instead.

---

#### `GET /api/v1/rack/<rack_uuid>`

**Scope required:** `rack_drawer`

Returns rack metadata plus a flat lightweight list of all items and batches stored in the rack.

**Response:**

```json
{
  "success": true,
  "rack": {
    "uuid": "RACK-UUID",
    "name": "Main Cabinet",
    "short_info": "Lab A shelf",
    "description": "",
    "color": "#3a86ff",
    "location": { "uuid": "LOC-UUID", "name": "Lab A", "color": "#28a745" },
    "rows": 5,
    "cols": 5,
    "stats": {
      "total_cells": 25,
      "unavailable": 2,
      "used": 8,
      "empty": 15
    }
  },
  "items": [
    {
      "type": "item_main",
      "name": "Arduino Mega",
      "item_uuid": "ABC123DEFG012345",
      "sku": "ARD-MEGA",
      "short_info": "",
      "drawer_cell": "R2-C3",
      "drawer_row": 2,
      "drawer_col": 3,
      "quantity": 10,
      "available": 8
    },
    {
      "type": "batch_override",
      "name": "Resistor Kit",
      "item_uuid": "XYZ789ABCDEF0123",
      "sku": "RES-KIT",
      "short_info": "Mixed values",
      "drawer_cell": "R1-C1",
      "drawer_row": 1,
      "drawer_col": 1,
      "quantity": 5,
      "available": 5
    }
  ]
}
```

`type` is `item_main` (item's primary location) or `batch_override` (batch has its own location in this rack).

---

#### `GET /api/v1/rack/<rack_uuid>/layout`

**Scope required:** `rack_drawer`

Returns the full cell-by-cell layout of a rack. Use this to recreate the visual grid.

**Cell states:**

| `state` | Meaning |
|---|---|
| `empty` | Cell is empty |
| `has_items` | Cell contains items |
| `merged_master` | Master of a rectangular merge — use `row_span`/`col_span` |
| `merged_away` | Hidden slave of a rectangular merge — skip when rendering |
| `group_master` | Master of a non-rectangular group — still rendered |
| `group_slave` | Member of a non-rectangular group — still rendered |
| `unavailable` | Cell marked unavailable. If this cell is also a merge master it will include `row_span` and `col_span` (same as `merged_master`). |

**Response:**

```json
{
  "success": true,
  "rack_uuid": "RACK-UUID",
  "rack_name": "Main Cabinet",
  "rack_color": "#3a86ff",
  "rows": 3,
  "cols": 3,
  "legend": { "empty": "...", "has_items": "...", "...": "..." },
  "cells": [
    {
      "row": 1, "col": 1, "cell_id": "R1-C1",
      "state": "merged_master",
      "short_info": "Power shelf",
      "row_span": 2, "col_span": 1,
      "item_count": 3
    },
    {
      "row": 2, "col": 1, "cell_id": "R2-C1",
      "state": "merged_away",
      "short_info": "",
      "master_cell": "R1-C1"
    },
    {
      "row": 1, "col": 2, "cell_id": "R1-C2",
      "state": "has_items",
      "short_info": "MCU row",
      "item_count": 2
    },
    {
      "row": 1, "col": 3, "cell_id": "R1-C3",
      "state": "empty",
      "short_info": ""
    }
  ]
}
```

**Row/col indices are 1-based** (R1-C1 through R{rows}-C{cols}).

For `merged_away` cells the `master_cell` field indicates which master cell they belong to.

For `group_master`/`group_slave` cells: `group_master` and `group_size` fields are included.

---

#### `GET /api/v1/rack/<rack_uuid>/drawer/<row>/<col>`

**Scope required:** `rack_drawer`

Get full contents of a single drawer cell. `row` and `col` are **1-based integers**.

Returns drawer state plus a detailed item list matching the visual-storage drawer popup.

**Response:**

```json
{
  "success": true,
  "rack_uuid": "RACK-UUID",
  "rack_name": "Main Cabinet",
  "row": 2,
  "col": 3,
  "cell_id": "R2-C3",
  "state": "has_items",
  "short_info": "MCU row",
  "items": [
    {
      "type": "item_main",
      "item_uuid": "ABC123DEFG012345",
      "name": "Arduino Mega",
      "sku": "ARD-MEGA",
      "short_info": "",
      "batches": [
        {
          "batch_uid": "ABC123DEFG012345-B01",
          "batch_label": "Batch 1",
          "quantity": 10,
          "available": 8,
          "sn_tracking": false
        }
      ]
    },
    {
      "type": "batch_override",
      "item_uuid": "XYZ789ABCDEF0123",
      "name": "Resistor Kit",
      "sku": "RES-KIT",
      "short_info": "Mixed values",
      "batch_uid": "XYZ789ABCDEF0123-B02",
      "batch_label": "Batch 2",
      "quantity": 5,
      "available": 5,
      "sn_tracking": false
    }
  ]
}
```

`type` values are the same as rack info. For `item_main` entries the `batches` array lists every batch stored in this drawer. For `batch_override` entries the batch fields are flat (one entry per batch).

**Error codes specific to location/rack:**

| Code | HTTP | Meaning |
|---|---|---|
| `RACK_NOT_FOUND` | 404 | No rack with that UUID |
| `LOCATION_NOT_FOUND` | 404 | No general location with that UUID |
| `MISSING_QUERY` | 400 | `q` parameter is empty |
| `INVALID_POSITION` | 400 | Row/col out of bounds (must be 1-based) |

---

### Typical ESP32 / Client Flow

**Lending flow:**

```
Boot / scan
│
├── GET /api/v1/lookup?q=<scanned_value>
│       Validate item, check availability, show name on display
│
├── (repeat for each item scanned)
│
├── POST /api/v1/lend  { "dry_run": true, "items": [...] }
│       Optional pre-submit validation — show preview on screen
│
└── POST /api/v1/lend  { "dry_run": false, "items": [...] }
        Commit — show session_id and success/failure per item
```

**Rack/drawer display flow:**

```
Find item location
│
├── GET /api/v1/location/search?q=<item_name_or_uuid>
│       Returns which rack + drawer the item lives in
│       (or which general location if no rack is assigned)
│
├── GET /api/v1/location/<uuid>          ← general location (no rack)
│       Metadata + racks at this location + items stored here directly
│
├── GET /api/v1/rack/<uuid>/layout
│       Fetch full rack grid to render on a display or web UI
│
└── GET /api/v1/rack/<uuid>/drawer/<row>/<col>
        Load full contents of the target drawer on demand
```

**Browser-rendered (recommended for ESP32):** Rather than parsing JSON on the ESP32 and building HTML server-side, the recommended pattern is to serve a static HTML/JS page from ESP32 flash (PROGMEM) and let the user's browser call the EM API directly. Because CORS is enabled on all `/api/v1/` endpoints, the browser can make authenticated requests from a page hosted on a different origin (the ESP32's IP). The ESP32 only needs to handle LED/indicator control; all heavy JSON processing stays in the browser.

---

### Setup — Enabling the API

1. **Admin: enable system-wide scope**
   - `Settings → System → Server API`
   - Turn on the scopes you want available (Item Search, Lending & Return, Location, Rack & Drawer)
   - Optionally adjust the rate limit (default 5 req/s)

2. **Admin: grant role permission**
   - `Settings → Users & Roles → [role] → Users API`
   - Enable **View API** and **Run API** for roles that need external API access
   - Ensure the role also has `Lending & Return → edit_lending` or `only_self_lending`

3. **User: generate API key and enable scopes**
   - `Settings → User API`
   - Toggle **Enable API** to generate a personal API key
   - **Copy the key immediately** — it is displayed only once and cannot be recovered (it is stored hashed, not in plain text)
   - Enable the scopes needed (must match what the admin enabled system-wide): Item Search, Lending & Return, and/or Location, Rack & Drawer
   - To rotate: click **Revoke & Regenerate Key** — the old key is invalidated instantly and a new one is shown once

---

## Internal API

These endpoints are used exclusively by the browser UI. They require an active login session and are **not intended for external access** — no token auth, no versioning, no stability guarantees.

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search-item` | Search items by name or UUID |

### Visual Storage

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/drawer/<rack_uuid>/<drawer_id>` | Items in a drawer |
| POST | `/api/drawer/toggle-availability` | Mark a drawer available/unavailable |
| POST | `/api/drawer/update-info` | Update drawer short-info label |
| POST | `/api/drawer/update-icon` | Set or clear a drawer icon |
| POST | `/api/drawer/move-items` | Bulk-move drawer contents |
| POST | `/api/drawer/swap-items` | Swap contents between two drawers |
| POST | `/api/rack/update-rack-icon` | Set or clear a rack icon |
| POST | `/api/rack/<rack_uuid>/merge-cells` | Merge rack cells into one slot |
| POST | `/api/rack/<rack_uuid>/split-cells` | Split a merged rack cell |

### Quick-Add

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/category/add` | Create a category inline |
| POST | `/api/footprint/add` | Create a footprint inline |
| POST | `/api/tag/add` | Create a tag inline |
| POST | `/api/location/add` | Create a location inline |

### Contacts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/contacts/persons` | List contact persons |
| GET | `/api/contacts/organizations` | List contact organizations |
| GET | `/api/contacts/all` | List all contacts (persons, orgs, groups) |

### Stickers & QR

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/item/<uuid>/sticker-preview/<template_id>` | Sticker HTML preview for an item |
| GET | `/api/item/<uuid>/sticker-print/<template_id>` | Sticker PDF for an item |
| GET | `/api/location/<uuid>/sticker-preview/<template_id>` | Sticker HTML preview for a location |
| GET | `/api/location/<uuid>/sticker-print/<template_id>` | Sticker PDF for a location |
| GET | `/api/rack/<uuid>/sticker-preview/<template_id>` | Sticker HTML preview for a rack |
| GET | `/api/rack/<uuid>/sticker-print/<template_id>` | Sticker PDF for a rack |
| GET | `/api/in-out/session/<lending_id>/session-qr-svg` | Inline SVG QR for a lending session |
| GET | `/api/in-out/session/<lending_id>/sticker-preview/<template_id>` | Sticker HTML preview for a lending session |
| GET | `/api/in-out/session/<lending_id>/sticker-print/<template_id>` | Sticker PDF for a lending session |

### Kanban

All Kanban endpoints require the user to have the `kanban → view_manage` role permission.

**Board access rules**

| Operation | Who can call it |
|-----------|----------------|
| Board/column/category management | Board owner only |
| Card & task create / edit / delete | Board owner or edit-shared users |
| Card & task read | Owner, edit-shared, view-shared, or public board visitors |
| Card file upload / delete | Owner, edit-shared, or view-shared users |
| Link / unlink share files on a card | Owner or edit-shared users (via card save) |

#### Boards

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/kanban` | Main Kanban board view (HTML); accepts `?board=<id>` to open a specific board |
| POST | `/kanban/boards` | Create a new board `{name}` |
| DELETE | `/kanban/boards/<id>` | Delete a board (owner only) |
| PUT | `/kanban/boards/<id>` | Update board settings (name, color, icon, visibility, share users, etc.) |
| GET | `/kanban/boards/<id>/settings` | Get board settings JSON (columns, categories, share lists) |
| POST | `/kanban/boards/<id>/reorder` | Reorder boards `{order: [id, ...]}` |
| POST | `/kanban/boards/<id>/status` | Set board visibility status `{status: shown|hidden|pinned}` |
| POST | `/kanban/boards/<id>/presence` | Heartbeat — report user presence; body `{editing_card_id}` |
| GET | `/kanban/boards/<id>/poll` | Long-poll for board events since a timestamp `?since=<ts>` |

#### Columns

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/kanban/boards/<id>/columns` | Add a column `{name, color, icon}` |
| PUT | `/kanban/columns/<id>` | Update a column |
| DELETE | `/kanban/columns/<id>` | Delete a column |
| POST | `/kanban/boards/<id>/columns/reorder` | Reorder columns `{order: [id, ...]}` |

#### Cards

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/kanban/columns/<id>/cards` | Create a card `{title}` |
| GET | `/kanban/cards/<id>` | Get full card detail (JSON) including tasks, attachments, and linked share files |
| PUT | `/kanban/cards/<id>` | Update a card — accepts `title`, `description`, `priority`, `category_id`, `label_color`, `start_date`, `due_date`, `completed_at`, `key_persons`, `share_file_ids` |
| DELETE | `/kanban/cards/<id>` | Delete a card and all its tasks and attachments |
| POST | `/kanban/cards/reorder` | Reorder cards across columns `{column_id, order: [id, ...]}` |

**`GET /kanban/cards/<id>` response shape (abbreviated):**

```json
{
  "id": 42,
  "title": "Design PCB",
  "description": "...",
  "priority": 3,
  "label_color": "#3b82f6",
  "category_id": 5,
  "category_name": "Hardware",
  "key_persons": [{"id": 1, "name": "Alice", "type": "user"}],
  "start_date": "2025-06-01",
  "due_date": "2025-06-30",
  "completed_at": "",
  "is_overdue": false,
  "tasks": [
    {"id": 10, "title": "Route power traces", "completed": false, "start_date": "", "due_date": "", "position": 0}
  ],
  "attachments": [
    {"id": 7, "filename": "kanban/42/schematic.pdf", "original_filename": "schematic.pdf",
     "file_type": "pdf", "file_size": 204800, "uploaded_at": "2025-06-08T10:00:00Z", "uploader_name": "Alice"}
  ],
  "share_files": [
    {"id": 3, "name": "Component Datasheet", "filename": "datasheet.pdf", "category": "item",
     "is_image": false, "ext": "pdf"}
  ],
  "created_at": "2025-06-01T09:00:00Z",
  "updated_at": "2025-06-08T10:00:00Z",
  "created_by_name": "Alice",
  "updated_by_name": "Alice"
}
```

**`PUT /kanban/cards/<id>` — `share_file_ids` field:**

Pass an array of shared file IDs to link to the card. Only files with category `item`, `project`, or `icon` are accepted. Pass an empty array `[]` to unlink all share files.

```json
{ "share_file_ids": [3, 7, 12] }
```

#### Card Attachments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/kanban/cards/<id>/upload` | Upload files to a card; multipart form field `files` (multiple); enforces Kanban upload settings |
| DELETE | `/kanban/cards/attachments/<id>` | Delete a card attachment by attachment ID |

Upload settings are configured at `Settings → System → File Upload Settings → Kanban Card Uploads`:
- Allowed extensions (default: `png,jpg,jpeg,txt,pdf`)
- Max file size in MB (default: 10 MB)
- Max files per upload batch (default: 5; `-1` = unlimited, `0` = uploads disabled)

#### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/kanban/cards/<id>/tasks` | Create a task `{title, start_date?, due_date?}` |
| PUT | `/kanban/tasks/<id>` | Update a task `{title?, completed?, start_date?, due_date?}` |
| DELETE | `/kanban/tasks/<id>` | Delete a task |
| POST | `/kanban/cards/<id>/tasks/reorder` | Reorder tasks `{order: [id, ...]}` |

#### Categories (board labels)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/kanban/boards/<id>/categories` | Create a category `{name}` |
| PUT | `/kanban/categories/<id>` | Rename a category |
| DELETE | `/kanban/categories/<id>` | Delete a category |
| POST | `/kanban/boards/<id>/categories/reorder` | Reorder categories |

---

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/available-fonts` | List custom font files in `static/custom/font/` |
| POST | `/api/settings/system/scan-share-files` | Scan share folder and register untracked files |
