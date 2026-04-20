# forge.config.yml Schema Specification

Version: 1 | Date: 2026-04-19

## Overview

A `forge.config.yml` schema defines the configuration surface of a Forge-managed tool.
It declares profile fields, config files with templated sections, verification commands,
and capability declarations. Schemas are stored in `config/schemas/<app>.yaml` and
referenced from the `tools.config_schema` column.

## Top-Level Keys

| Key              | Type    | Required | Description                                      |
|------------------|---------|----------|--------------------------------------------------|
| `schema_version` | integer | yes      | Schema format version. Currently `1`.            |
| `app`            | string  | yes      | Tool slug (e.g. `career-ops`).                   |
| `profile_fields` | array   | yes      | User-specific fields auto-filled during setup.   |
| `config_files`   | array   | yes      | Files the tool expects the user to configure.    |
| `verification`   | object  | no       | Command to verify a valid configuration.         |
| `capabilities`   | object  | no       | Declared permissions (future governance).        |

## profile_fields[]

Each entry collects a piece of user identity used across config files.

| Key        | Type   | Required | Description                                          |
|------------|--------|----------|------------------------------------------------------|
| `key`      | string | yes      | Identifier (e.g. `full_name`).                       |
| `prompt`   | string | yes      | Human-readable prompt shown during setup.            |
| `type`     | string | yes      | One of: `string`, `url`, `email`, `phone`.           |
| `source`   | string | no       | Auto-fill source: `forge.user.name`, `forge.user.email`, etc. |
| `required` | bool   | yes      | Whether the field must be provided.                  |

## config_files[]

Each entry describes a file the tool needs, optionally generated from a template.

| Key        | Type   | Required | Description                                        |
|------------|--------|----------|----------------------------------------------------|
| `path`     | string | yes      | Relative path from tool root.                      |
| `template` | string | no       | Path to example/template file to copy from.        |
| `format`   | string | no       | File format hint: `yaml`, `markdown`, `text`.      |
| `sections` | array  | no       | Structured sections within the file (see below).   |

### config_files[].sections[]

| Key      | Type   | Required | Description                             |
|----------|--------|----------|-----------------------------------------|
| `name`   | string | yes      | Section identifier (e.g. `candidate`).  |
| `fields` | array  | yes      | Fields within this section.             |

### config_files[].sections[].fields[]

| Key        | Type   | Required | Description                                              |
|------------|--------|----------|----------------------------------------------------------|
| `key`      | string | yes      | Field name in the config file.                           |
| `type`     | string | yes      | One of: `string`, `url`, `list`, `freeform_file`, `object_list`. |
| `prompt`   | string | no       | Description shown during guided setup.                   |
| `required` | bool   | no       | Defaults to `false`.                                     |
| `items`    | object | no       | For `list`/`object_list`: describes list item structure.  |

**Type definitions:**
- `string` -- single scalar value
- `url` -- validated URL string
- `list` -- array of strings
- `freeform_file` -- entire file is user-authored free-form content (e.g. a CV)
- `object_list` -- array of objects, each described by `items.fields`

## verification

| Key               | Type   | Required | Description                                 |
|-------------------|--------|----------|---------------------------------------------|
| `command`         | string | yes      | Shell command to run (e.g. `npm run doctor`). |
| `success_pattern` | string | yes      | Regex matched against stdout for success.   |

## capabilities

Declared permissions for future governance. **Not enforced in schema_version 1.**

| Key       | Type  | Required | Description                                        |
|-----------|-------|----------|----------------------------------------------------|
| `network` | array | no       | Domains the tool may contact (e.g. `["*.greenhouse.io"]`). |
| `reads`   | array | no       | Paths/globs the tool reads (e.g. `["config/**"]`). |
| `writes`  | array | no       | Paths/globs the tool writes (e.g. `["output/**"]`).|

## Example (minimal)

```yaml
schema_version: 1
app: my-tool
profile_fields:
  - key: full_name
    prompt: "Your full name"
    type: string
    source: forge.user.name
    required: true
config_files:
  - path: config/settings.yml
    template: config/settings.example.yml
    sections:
      - name: general
        fields:
          - key: api_key
            type: string
            required: true
verification:
  command: "npm run doctor"
  success_pattern: "All checks passed"
capabilities:
  network: ["api.example.com"]
  reads: ["config/**"]
  writes: ["output/**"]
```
