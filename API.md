# Pennsieve API Reference

API calls used across the migrationtools codebase, organized by domain.

**Base URLs:**
- `https://api.pennsieve.io` — Primary API (v1)
- `https://api2.pennsieve.io` — Metadata/Records API (v2)

---

## Authentication

Two authentication methods are used throughout the codebase:

### 1. API Key (Query Parameter)

Used by older/simpler scripts. The API key is passed directly as a query parameter.

```
?api_key={PENNSIEVE_API_KEY}
```

**Source:** `PENNSIEVE_API_KEY` environment variable.

### 2. Bearer Token (Cognito)

Used by newer scripts that take `--api-key` and `--api-secret` arguments. A two-step process:

#### Step 1: Get Cognito Config

```
GET /authentication/cognito-config
```

| Field | Details |
|-------|---------|
| **Auth** | None |
| **Headers** | None required |
| **Response** | `{ "tokenPool": { "appClientId": "..." }, "region": "us-east-1" }` |
| **Used in** | `upload_file.py:45`, `add_publications.py:46`, `delete_publications.py:41`, `delete_models.py:49`, `omop_populator.py:66`, `model_populator.py:80`, `update_datasets.py:49` |

#### Step 2: Exchange Credentials via Cognito

Uses the AWS `boto3` Cognito IDP client (not an HTTP call to Pennsieve):

```python
cognito_idp_client.initiate_auth(
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={"USERNAME": api_key, "PASSWORD": api_secret},
    ClientId=cognito_app_client_id,
)
```

**Returns:** `AuthenticationResult.AccessToken` — used as `Authorization: Bearer {token}` in subsequent requests.

---

## Datasets

### List All Datasets (Paginated)

```
GET /datasets/paginated
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Query Params** | `limit` (default: 25), `offset` (default: 0), `orderBy` (e.g., `Name`), `orderDirection` (`Asc`/`Desc`), `includeBannerUrl` (`true`/`false`), `includePublishedDataset` (`true`/`false`) |
| **Headers** | `accept: */*` or `application/json` |
| **Response** | `{ "datasets": [...], "totalCount": <int> }` |
| **Pagination** | Offset-based: increment `offset` by `limit` until `offset >= totalCount` |
| **Used in** | `helpers.py:112`, `upload_file.py:92`, `add_publications.py:151`, `delete_publications.py:109`, `delete_models.py:137`, `omop_populator.py:200`, `model_populator.py:132`, `update_datasets.py:124` |

### Update Dataset Metadata

```
PUT /datasets/{dataset_id}
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id` — the dataset's ID (e.g., `N:dataset:uuid`) |
| **Body** | JSON object with any combination of: `name`, `description`, `license`, `tags` |
| **Headers** | `Content-Type: application/json`, `accept: */*` |
| **Used in** | `rename.py:32` (name), `add_license.py:39` (license), `manage_datasets.py:154` (description, tags, name), `update_datasets.py:222` (description), `update_datasets.py:237` (tags) |

**Example payloads:**
```json
{"name": "PennEPI00215"}
{"license": "Creative Commons Attribution"}
{"description": "...", "tags": ["epilepsy", "human"], "name": "PennEPI00215"}
```

### Update Dataset Banner Image

```
PUT /datasets/{dataset_id}/banner
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id` |
| **Body** | Multipart form data: `banner` field with `(filename, file_bytes, content_type)` |
| **Content Types** | `image/png`, `image/jpeg`, `image/gif` |
| **Headers** | `accept: */*` (do NOT set `Content-Type` — let `requests` set multipart boundary) |
| **Used in** | `add_image.py:32`, `update_datasets.py:338` |

### Update Dataset Readme

```
PUT /datasets/{dataset_id}/readme
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id` |
| **Body** | `{ "readme": "<text>" }` |
| **Used in** | `manage_datasets.py:184`, `update_datasets.py:254` |

### Get Dataset Storage Credentials

```
GET /datasets/{dataset_id}/storage
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `dataset_id` (URL-encoded) |
| **Response** | S3 credentials for direct upload |
| **Used in** | `upload_file.py:122` |

---

## Contributors

### Delete Contributor from Dataset

```
DELETE /datasets/{dataset_id}/contributors/{contributor_id}
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id`, `contributor_id` (integer) |
| **Status Codes** | `200`/`204` = success, `404` = not found (treated as OK) |
| **Used in** | `manage_datasets.py:118`, `update_datasets.py:184` |

### Add Contributor to Dataset

```
PUT /datasets/{dataset_id}/contributors
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id` |
| **Body** | `{ "contributorId": <int> }` |
| **Used in** | `manage_datasets.py:131`, `update_datasets.py:201` |

---

## Collaborators & Ownership

### Update Dataset Owner

```
PUT /datasets/{dataset_id}/collaborators/owner
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id` |
| **Body** | `{ "id": "N:user:uuid", "role": "owner" }` |
| **Used in** | `manage_datasets.py:169`, `update_datasets.py:272` |

### Add Team as Collaborator

```
PUT /datasets/{dataset_id}/collaborators/teams
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id` |
| **Body** | `{ "id": "<team_id>", "role": "viewer" \| "editor" \| "manager" }` |
| **Used in** | `rename.py:177`, `update_datasets.py:298` |

---

## External Publications (DOIs)

### Add Publication to Dataset

```
PUT /datasets/{dataset_id}/external-publications
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `dataset_id` |
| **Query Params** | `doi` (e.g., `10.1016/j.example.2025.01.001`), `relationshipType` (e.g., `IsDescribedBy`) |
| **Body** | None |
| **Used in** | `add_publications.py:195` |

**Valid relationship types** (DataCite schema):
`IsCitedBy`, `Cites`, `IsSupplementTo`, `IsSupplementedBy`, `IsContinuedBy`, `Continues`, `IsDescribedBy`, `Describes`, `HasMetadata`, `IsMetadataFor`, `HasVersion`, `IsVersionOf`, `IsNewVersionOf`, `IsPreviousVersionOf`, `IsPartOf`, `HasPart`, `IsReferencedBy`, `References`, `IsDocumentedBy`, `Documents`, `IsCompiledBy`, `Compiles`, `IsVariantFormOf`, `IsOriginalFormOf`, `IsIdenticalTo`, `IsReviewedBy`, `Reviews`, `IsDerivedFrom`, `IsSourceOf`, `IsRequiredBy`, `Requires`, `IsObsoletedBy`, `Obsoletes`

### Delete Publication from Dataset

```
DELETE /datasets/{dataset_id}/external-publications
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `dataset_id` |
| **Query Params** | `doi`, `relationshipType` |
| **Status Codes** | `200`/`204` = success, `404` = not found (treated as OK) |
| **Used in** | `delete_publications.py:152` |

---

## Packages (Files & Folders)

### List Dataset Packages (Paginated)

```
GET /datasets/{dataset_id}/packages
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Path Params** | `dataset_id` (URL-encoded) |
| **Query Params** | `pageSize` (default: 1000), `includeSourceFiles` (`true`/`false`), `cursor` (for pagination) |
| **Response** | `{ "packages": [...], "cursor": "<next_cursor>" \| null }` |
| **Pagination** | Cursor-based: if `cursor` is non-null, append `&cursor={value}` for next page |
| **Used in** | `helpers.py:141`, `omop_populator.py:235`, `model_populator.py:158` |

### Download Package Manifest

Returns presigned download URLs for package files.

```
POST /packages/download-manifest
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) or Bearer token |
| **Body** | `{ "nodeIds": ["N:package:uuid", ...] }` |
| **Headers** | `accept: application/json`, `content-type: application/json` |
| **Response** | `{ "data": [{ "url": "<presigned_s3_url>", ... }] }` |
| **Used in** | `helpers.py:171`, `helpers.py:196`, `omop_populator.py:351`, `model_populator.py:377`, `download_mef_samples.py:222` |

**Follow-up:** The returned `url` is then fetched with a plain `GET` (no auth) to download the actual file content.

### Rename Package

```
PUT /packages/{package_id}
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) |
| **Path Params** | `package_id` (nodeId) |
| **Query Params** | `updateStorage=false` |
| **Body** | `{ "name": "<new_name>" }` |
| **Used in** | `cleanup_duplicates.py:160`, `rename.py:57` |

### Delete Package(s)

```
POST /data/delete
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) |
| **Body** | `{ "things": ["N:package:uuid", ...] }` |
| **Headers** | `accept: */*`, `content-type: application/json` |
| **Used in** | `cleanup_duplicates.py:137`, `manage_datasets.py:432` |

### Move Packages to Folder

```
POST /data/move
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) |
| **Body** | `{ "destination": "<archive_folder_id>", "things": ["node_id_1", "node_id_2", ...] }` |
| **Used in** | `manage_datasets.py:618` |

### Create Collection (Folder)

```
POST /packages
```

| Field | Details |
|-------|---------|
| **Auth** | API key (query param) |
| **Body** | `{ "name": "archive", "dataset": "<dataset_id>", "packageType": "Collection" }` |
| **Response** | `{ "content": { "id": "..." } }` |
| **Used in** | `manage_datasets.py:226` |

---

## File Upload

Three-step upload process:

### Step 1: Request Upload (Get Presigned URL)

```
POST /files/upload/preview
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Body** | See below |
| **Response** | `{ "packages": [{ "url": "<presigned_url>", "fields": {...}, "packageId": "...", "importId": "..." }] }` |
| **Used in** | `upload_file.py:179` |

**Request body:**
```json
{
  "datasetId": "N:dataset:uuid",
  "destinationId": "folder_id (optional)",
  "files": [
    {
      "fileName": "example.png",
      "size": 1234567,
      "uploadId": 1
    }
  ]
}
```

### Step 2: Upload to S3

Uses the presigned URL from Step 1.

**If `fields` are returned** (multipart form upload):
```
POST {presigned_url}
```
| Field | Details |
|-------|---------|
| **Body** | Form data with `fields` from Step 1 response + `file` field |
| **Used in** | `upload_file.py:205` |

**If no `fields`** (direct PUT):
```
PUT {presigned_url}
```
| Field | Details |
|-------|---------|
| **Headers** | `Content-Type: application/octet-stream` |
| **Body** | Raw file bytes |
| **Used in** | `upload_file.py:208` |

### Step 3: Complete Upload

```
POST /files/upload/complete
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Body** | See below |
| **Used in** | `upload_file.py:239` |

**Request body:**
```json
{
  "datasetId": "N:dataset:uuid",
  "destinationId": "folder_id (optional)",
  "files": [
    {
      "uploadId": 1,
      "fileName": "example.png",
      "size": 1234567,
      "packageId": "from_step_1_response",
      "importId": "from_step_1_response"
    }
  ]
}
```

---

## Metadata Models (API v2)

All metadata endpoints use `https://api2.pennsieve.io` and Bearer token auth.

The `dataset_id` parameter must be URL-encoded (e.g., `N%3Adataset%3Auuid`).

### List All Models for Dataset

```
GET /metadata/models
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Query Params** | `dataset_id` (URL-encoded) |
| **Response** | Array of `{ "model": { "id": "...", "name": "...", ... }, ... }` |
| **Used in** | `delete_models.py:169`, `omop_populator.py:618`, `model_populator.py:196` |

### Get Model Schema

```
GET /metadata/models/{model_id}
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `model_id` (UUID) |
| **Query Params** | `dataset_id` (URL-encoded) |
| **Response** | JSON schema definition for the model |
| **Used in** | `get_model_schema.py:47`, `cleanup_records.py:26` (referenced) |

### Create Model from Template

```
POST /metadata/templates/{template_id}/models
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `template_id` (UUID) |
| **Query Params** | `dataset_id` (URL-encoded), `version` (int, default: 1) |
| **Body** | `{ "name": "model_name", "display_name": "Display Name", "description": "..." }` |
| **Response** | `{ "model": { "id": "...", ... } }` |
| **Error Handling** | `400` with `"duplicate model name"` in message body — fall back to finding existing model |
| **Used in** | `omop_populator.py:657`, `model_populator.py:247` |

### Delete Model

```
DELETE /metadata/models/{model_id}
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `model_id` (UUID) |
| **Query Params** | `dataset_id` (URL-encoded), `force` (`true`/`false`) |
| **Used in** | `delete_models.py:185` |

---

## Metadata Records (API v2)

### Search Records (Paginated)

```
GET /metadata/models/{model_id}/records/search
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `model_id` (UUID) |
| **Query Params** | `dataset_id` (URL-encoded), `page_size` (int), `cursor` (optional) |
| **Response** | `{ "records": [{ "id": "...", ... }], "cursor": "<next>" \| null }` |
| **Pagination** | Cursor-based |
| **Used in** | `cleanup_records.py:30` |

### Create Records

```
POST /metadata/models/{model_id}/records
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `model_id` (UUID) |
| **Query Params** | `dataset_id` (URL-encoded) |
| **Body** | `{ "records": [{ "field1": "value1", ... }, ...] }` |
| **Used in** | `omop_populator.py:709`, `model_populator.py:597` |

### Delete Record

```
DELETE /metadata/models/{model_id}/records/{record_id}
```

| Field | Details |
|-------|---------|
| **Auth** | Bearer token |
| **Path Params** | `model_id` (UUID), `record_id` (UUID) |
| **Query Params** | `dataset_id` (URL-encoded), `force=true` |
| **Used in** | `cleanup_records.py:38` |

---

## Pagination Patterns

### Offset-based (Datasets)

Used by `GET /datasets/paginated`:

```
offset=0, limit=25  →  offset=25, limit=25  →  ...
Stop when: offset >= totalCount
```

### Cursor-based (Packages, Records)

Used by `GET /datasets/{id}/packages` and `GET /metadata/models/{id}/records/search`:

```
Initial call (no cursor)  →  check response cursor  →  append &cursor={value}  →  repeat
Stop when: cursor is null/empty
```

---

## Common Headers

**Standard JSON requests:**
```
accept: application/json (or */*)
content-type: application/json
Authorization: Bearer {access_token}
```

**File uploads (multipart):**
```
accept: */*
Authorization: Bearer {access_token}
(Content-Type set automatically by requests library)
```

---

## Error Handling Patterns

| Status | Meaning | Common Handling |
|--------|---------|-----------------|
| 200 | Success | Parse JSON response |
| 204 | Success (No Content) | Treat as success, no body to parse |
| 400 | Bad request | Check for `"duplicate model name"` message; fall back to finding existing resource |
| 404 | Not found | Often treated as OK (e.g., deleting something that doesn't exist) |
| 401/403 | Auth failure | Re-authenticate or check credentials |

Most calls use `response.raise_for_status()` to convert HTTP errors to Python exceptions.
