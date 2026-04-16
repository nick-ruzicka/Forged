"""Salesforce read-only connector for ForgeData.

Graceful degradation is non-negotiable: when required env vars are missing,
every public method returns {"error": "Salesforce not configured",
"configured": False} instead of raising. This lets the pipeline's red_team and
qa_tester agents branch on configured=False without special-casing exceptions.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger("forge.forgedata.salesforce")

_NOT_CONFIGURED: Dict[str, Any] = {
    "error": "Salesforce not configured",
    "configured": False,
}


def _esc(value: str) -> str:
    """Minimal SOQL escaping — backslash and single-quote only."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _snake(row: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a Salesforce response row (minus 'attributes') into snake_case."""
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if k == "attributes":
            continue
        if isinstance(v, dict):
            inner_name = v.get("Name")
            if inner_name is not None:
                out[_camel_to_snake(k) + "_name"] = inner_name
            inner_id = v.get("Id")
            if inner_id is not None:
                out[_camel_to_snake(k) + "_id"] = inner_id
            continue
        out[_camel_to_snake(k)] = v
    return out


def _camel_to_snake(name: str) -> str:
    buf: List[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            buf.append("_")
        buf.append(ch.lower())
    return "".join(buf)


class SalesforceConnector:
    _cache_client = None
    _cache_ts = 0.0
    _CACHE_TTL_SEC = 30 * 60

    def __init__(self):
        self.username = os.environ.get("SALESFORCE_USERNAME") or ""
        self.password = os.environ.get("SALESFORCE_PASSWORD") or ""
        self.token = os.environ.get("SALESFORCE_TOKEN") or ""
        self.domain = os.environ.get("SALESFORCE_DOMAIN") or "login.salesforce.com"

    def is_configured(self) -> bool:
        return bool(self.username and self.password and self.token)

    def connect(self):
        """Return a cached `simple_salesforce.Salesforce` client, or None when
        not configured. Cache lives 30 minutes (session tokens last longer but
        we refresh conservatively)."""
        if not self.is_configured():
            return None
        now = time.time()
        cls = SalesforceConnector
        if cls._cache_client is not None and (now - cls._cache_ts) < cls._CACHE_TTL_SEC:
            return cls._cache_client
        try:
            from simple_salesforce import Salesforce  # type: ignore
        except ImportError as e:
            log.warning("simple-salesforce not installed: %s", e)
            return None
        domain_arg = self.domain.replace(".salesforce.com", "")
        if domain_arg.endswith(".my"):
            domain_arg = domain_arg
        try:
            client = Salesforce(
                username=self.username,
                password=self.password,
                security_token=self.token,
                domain=domain_arg or "login",
            )
            cls._cache_client = client
            cls._cache_ts = now
            return client
        except Exception as e:
            log.warning("salesforce connect failed: %s", e)
            return None

    def is_connected(self) -> bool:
        return self.connect() is not None

    # ---- Queries ----

    def get_accounts(self, search: Optional[str] = None, limit: int = 20):
        if not self.is_configured():
            return dict(_NOT_CONFIGURED)
        client = self.connect()
        if client is None:
            return {"error": "Salesforce connection failed", "configured": True, "connected": False}
        lim = max(1, min(int(limit or 20), 200))
        where = "IsDeleted=false"
        if search:
            where += f" AND Name LIKE '%{_esc(search)}%'"
        soql = (
            "SELECT Id,Name,Type,Industry,AnnualRevenue,NumberOfEmployees,"
            "OwnerId,Owner.Name,LastActivityDate,CreatedDate "
            f"FROM Account WHERE {where} LIMIT {lim}"
        )
        try:
            resp = client.query(soql)
        except Exception as e:
            log.warning("get_accounts query failed: %s", e)
            return {"error": f"query failed: {e}", "configured": True, "connected": True}
        records = resp.get("records", []) if isinstance(resp, dict) else []
        return [_snake(r) for r in records]

    def get_opportunities(
        self,
        account_id: Optional[str] = None,
        stage: Optional[str] = None,
        limit: int = 20,
    ):
        if not self.is_configured():
            return dict(_NOT_CONFIGURED)
        client = self.connect()
        if client is None:
            return {"error": "Salesforce connection failed", "configured": True, "connected": False}
        lim = max(1, min(int(limit or 20), 200))
        where = ["IsDeleted=false"]
        if account_id:
            where.append(f"AccountId='{_esc(account_id)}'")
        if stage:
            where.append(f"StageName='{_esc(stage)}'")
        soql = (
            "SELECT Id,Name,AccountId,Account.Name,StageName,Amount,CloseDate,"
            "Probability,OwnerId,Owner.Name,LastModifiedDate,CreatedDate "
            f"FROM Opportunity WHERE {' AND '.join(where)} "
            f"ORDER BY CloseDate ASC NULLS LAST LIMIT {lim}"
        )
        try:
            resp = client.query(soql)
        except Exception as e:
            log.warning("get_opportunities query failed: %s", e)
            return {"error": f"query failed: {e}", "configured": True, "connected": True}
        records = resp.get("records", []) if isinstance(resp, dict) else []
        return [_snake(r) for r in records]

    def get_contacts(
        self,
        account_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
    ):
        if not self.is_configured():
            return dict(_NOT_CONFIGURED)
        client = self.connect()
        if client is None:
            return {"error": "Salesforce connection failed", "configured": True, "connected": False}
        lim = max(1, min(int(limit or 20), 200))
        where = ["IsDeleted=false"]
        if account_id:
            where.append(f"AccountId='{_esc(account_id)}'")
        if search:
            s = _esc(search)
            where.append(f"(Name LIKE '%{s}%' OR Email LIKE '%{s}%')")
        soql = (
            "SELECT Id,FirstName,LastName,Name,Title,Email,Phone,AccountId,"
            "Account.Name,OwnerId,Owner.Name,LastActivityDate,CreatedDate "
            f"FROM Contact WHERE {' AND '.join(where)} LIMIT {lim}"
        )
        try:
            resp = client.query(soql)
        except Exception as e:
            log.warning("get_contacts query failed: %s", e)
            return {"error": f"query failed: {e}", "configured": True, "connected": True}
        records = resp.get("records", []) if isinstance(resp, dict) else []
        return [_snake(r) for r in records]

    def get_activities(self, account_id: str, limit: int = 10):
        if not self.is_configured():
            return dict(_NOT_CONFIGURED)
        if not account_id:
            return {"error": "account_id required", "configured": True}
        client = self.connect()
        if client is None:
            return {"error": "Salesforce connection failed", "configured": True, "connected": False}
        lim = max(1, min(int(limit or 10), 200))
        soql = (
            "SELECT Id,Subject,ActivityDate,Status,OwnerId,Owner.Name,WhatId,What.Name "
            f"FROM Task WHERE WhatId='{_esc(account_id)}' "
            f"ORDER BY ActivityDate DESC NULLS LAST LIMIT {lim}"
        )
        try:
            resp = client.query(soql)
        except Exception as e:
            log.warning("get_activities query failed: %s", e)
            return {"error": f"query failed: {e}", "configured": True, "connected": True}
        records = resp.get("records", []) if isinstance(resp, dict) else []
        return [_snake(r) for r in records]
