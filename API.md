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

If a scope is disabled system-wide, **no user** can use it regardless of their personal settings.

**Level 2 — Per-user (Settings → User API)**

Each user independently enables the scopes they need:

| User field | Scope |
|------------|-------|
| `api_item_search` | Item Search & Information |
| `api_lending_return` | Lending & Return |

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

### Typical ESP32 / Client Flow

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

---

### Setup — Enabling the API

1. **Admin: enable system-wide scope**
   - `Settings → System → Server API`
   - Turn on the scopes you want available (Item Search, Lending & Return)
   - Optionally adjust the rate limit (default 5 req/s)

2. **Admin: grant role permission**
   - `Settings → Users & Roles → [role] → Users API`
   - Enable **View API** and **Run API** for roles that need external API access
   - Ensure the role also has `Lending & Return → edit_lending` or `only_self_lending`

3. **User: generate API key and enable scopes**
   - `Settings → User API`
   - Toggle **Enable API** to generate a personal API key
   - Enable the scopes needed (must match what the admin enabled system-wide)
   - Copy the API key — it is shown only once (use the Show button)
   - To rotate: click **Revoke** then re-enable

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

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/available-fonts` | List custom font files in `static/custom/font/` |
| POST | `/api/settings/system/scan-share-files` | Scan share folder and register untracked files |
