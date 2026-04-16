"""ForgeData layer.

Exposes governed, read-only business data to apps via `window.ForgeAPI.data.*`.
Every read is logged to `forge_data_reads`. No write operations in v1.

No-creds contract: when the configured source (Salesforce) is missing env
vars, every route returns `{"error": "Salesforce not configured",
"configured": false}` — NOT empty arrays, NOT exceptions. Downstream
pipeline agents (red_team, qa_tester) branch on `configured === false`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from api import db
from api.connectors.salesforce import SalesforceConnector

log = logging.getLogger("forge.forgedata")

forgedata_bp = Blueprint("forgedata", __name__)


_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS forge_data_reads (
  id SERIAL PRIMARY KEY,
  tool_id INTEGER,
  user_email TEXT,
  source TEXT,
  query_type TEXT,
  params TEXT,
  result_count INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
)
"""


def _ensure_table() -> None:
    try:
        with db.get_db(dict_cursor=False) as cur:
            cur.execute(_TABLE_DDL)
    except Exception as e:
        log.warning("forge_data_reads table init failed: %s", e)


_ensure_table()


def _log_read(source: str, query_type: str, params: Dict[str, Any], result_count: int) -> None:
    tool_id_raw = request.headers.get("X-Tool-Id")
    try:
        tool_id = int(tool_id_raw) if tool_id_raw else None
    except (TypeError, ValueError):
        tool_id = None
    user_email = request.headers.get("X-User-Email") or None
    try:
        with db.get_db(dict_cursor=False) as cur:
            cur.execute(
                """INSERT INTO forge_data_reads
                   (tool_id, user_email, source, query_type, params, result_count)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (tool_id, user_email, source, query_type, json.dumps(params or {}), int(result_count)),
            )
    except Exception as e:
        log.warning("forge_data_reads insert failed: %s", e)


def _wrap(source: str, query_type: str, params: Dict[str, Any], result):
    """Shape the response and log the read.

    - On no-creds / error shape (dict with `configured` key), pass through.
    - On list result, wrap as `{data, count, source}` and log count.
    """
    if isinstance(result, dict) and "configured" in result:
        _log_read(source, query_type, params, 0)
        return jsonify(result)
    if isinstance(result, list):
        _log_read(source, query_type, params, len(result))
        return jsonify({"data": result, "count": len(result), "source": source})
    _log_read(source, query_type, params, 0)
    return jsonify(result)


# -------------------- Status --------------------

@forgedata_bp.route("/api/forgedata/status", methods=["GET"])
def status():
    sf = SalesforceConnector()
    configured = sf.is_configured()
    connected = sf.is_connected() if configured else False
    return jsonify({
        "salesforce": {"configured": configured, "connected": connected}
    })


# -------------------- Salesforce routes --------------------

@forgedata_bp.route("/api/forgedata/salesforce/accounts", methods=["GET"])
def sf_accounts():
    search = request.args.get("search") or None
    try:
        limit = int(request.args.get("limit") or 20)
    except ValueError:
        limit = 20
    params = {"search": search, "limit": limit}
    result = SalesforceConnector().get_accounts(search=search, limit=limit)
    return _wrap("salesforce", "accounts", params, result)


@forgedata_bp.route("/api/forgedata/salesforce/opportunities", methods=["GET"])
def sf_opportunities():
    account_id = request.args.get("account_id") or None
    stage = request.args.get("stage") or None
    try:
        limit = int(request.args.get("limit") or 20)
    except ValueError:
        limit = 20
    params = {"account_id": account_id, "stage": stage, "limit": limit}
    result = SalesforceConnector().get_opportunities(account_id=account_id, stage=stage, limit=limit)
    return _wrap("salesforce", "opportunities", params, result)


@forgedata_bp.route("/api/forgedata/salesforce/contacts", methods=["GET"])
def sf_contacts():
    account_id = request.args.get("account_id") or None
    search = request.args.get("search") or None
    try:
        limit = int(request.args.get("limit") or 20)
    except ValueError:
        limit = 20
    params = {"account_id": account_id, "search": search, "limit": limit}
    result = SalesforceConnector().get_contacts(account_id=account_id, search=search, limit=limit)
    return _wrap("salesforce", "contacts", params, result)


@forgedata_bp.route("/api/forgedata/salesforce/activities", methods=["GET"])
def sf_activities():
    account_id = request.args.get("account_id") or ""
    try:
        limit = int(request.args.get("limit") or 10)
    except ValueError:
        limit = 10
    params = {"account_id": account_id, "limit": limit}
    if not account_id:
        _log_read("salesforce", "activities", params, 0)
        return jsonify({"error": "account_id required", "configured": SalesforceConnector().is_configured()}), 400
    result = SalesforceConnector().get_activities(account_id=account_id, limit=limit)
    return _wrap("salesforce", "activities", params, result)
