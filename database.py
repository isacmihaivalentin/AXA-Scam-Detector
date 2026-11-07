"""Read-only catalog access for the API. Run this module to initialize a demo database."""
import json
import logging
import os
import re
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger("axa")
DEFAULT_DB = ROOT / "axa.sqlite3"

# Carried over from the supplied archive. These are known-list hints; no current
# verification is implied. An entry in the database supersedes its fallback brand.
FALLBACK_BRANDS = (
    ("BCR", "bank", "bcr.ro", "george.bcr.ro"),
    ("Banca Transilvania", "bank", "bancatransilvania.ro"),
    ("ING", "bank", "ing.ro", "homebank.ro"),
    ("Raiffeisen", "bank", "raiffeisen.ro"), ("CEC", "bank", "cec.ro"),
    ("UniCredit", "bank", "unicredit.ro"), ("Revolut", "bank", "revolut.com"),
    ("Salt Bank", "bank", "salt.bank"),
    ("Sameday", "courier", "sameday.ro"), ("Fan Courier", "courier", "fancourier.ro"),
    ("Cargus", "courier", "cargus.ro"), ("Poșta Română", "courier", "posta-romana.ro"),
    ("DHL", "courier", "dhl.ro"), ("OLX", "marketplace", "olx.ro"),
    ("eMAG", "retail", "emag.ro"), ("ANAF", "government", "anaf.ro"),
    ("Ghiseul.ro", "government", "ghiseul.ro"), ("Enel", "utility", "enel.ro"),
    ("PPC Energy", "utility", "ppcenergy.ro"), ("Hidroelectrica", "utility", "hidroelectrica.ro"),
    ("Electrica Furnizare", "utility", "electricafurnizare.ro"), ("E.ON", "utility", "eon.ro"),
    ("Digi", "telecom", "digi.ro"), ("Orange", "telecom", "orange.ro"),
    ("Vodafone", "telecom", "vodafone.ro"), ("Discord", "online_service", "discord.com"),
)
REVIEWED_DOMAINS = (
    ("BCR", "bank", "bcr.ro", "https://www.bcr.ro/ro/persoane-fizice"),
    ("ING", "bank", "ing.ro", "https://ing.ro/persoane-fizice"),
    ("ING", "bank", "homebank.ro", "https://ing.ro/persoane-fizice"),
    ("Sameday", "courier", "sameday.ro", "https://sameday.ro/"),
    ("OLX", "marketplace", "olx.ro", "https://www.olx.ro/"),
    ("Discord", "online_service", "discord.com", "https://discord.com/nitro"),
    ("eMAG", "retail", "emag.ro", "https://www.emag.ro/help/wp-content/uploads/2025/02/TERMENI-SI-CONDITII-SPECIALE-PRIVIND-Utilizarea-serviciului-PAYBYCLICK-si-PAY-ON-TIME.pdf"),
)


def brand_key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower().translate(str.maketrans("ăâîșț", "aaist")))


@dataclass(frozen=True)
class BrandDomain:
    name: str
    category: str
    domain: Optional[str]
    verification_source: Optional[str] = None
    verified_at: Optional[str] = None
    aliases: tuple[str, ...] = ()


STATIC_CATALOG = tuple(
    BrandDomain(name, category, domain)
    for name, category, *domains in FALLBACK_BRANDS
    for domain in domains
)


@contextmanager
def catalog_connection():
    dsn = os.environ.get("AXA_DATABASE_URL", "").strip()
    if dsn:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=2, prepare_threshold=None) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '1500ms'")
            conn.execute("SET LOCAL search_path TO axa, pg_catalog")
            yield conn, "postgresql"
    else:
        path = Path(os.environ.get("AXA_SQLITE_PATH") or DEFAULT_DB).expanduser().resolve()
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as conn:
            yield conn, "sqlite"


def reviewed_aliases(conn, backend):
    if backend == "sqlite":
        available = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='brand_aliases'"
        ).fetchone()
    else:
        available = conn.execute(
            "SELECT COALESCE(has_table_privilege(to_regclass('axa.brand_aliases'), 'SELECT'), false)"
        ).fetchone()
        available = available and available[0]
    aliases = {}
    if available:
        for key, alias in conn.execute(
            "SELECT b.normalized_name, a.alias FROM brand_aliases a JOIN brands b ON b.id = a.brand_id "
            "WHERE a.reviewed_at IS NOT NULL AND a.verification_source <> '' ORDER BY a.normalized_alias"
        ).fetchall():
            aliases.setdefault(key, []).append(alias)
    return aliases


def load_catalog():
    """Return (brand/domain entries, check status). Unavailable stores use archive hints."""
    try:
        with catalog_connection() as (conn, backend):
            rows = conn.execute(
                "SELECT b.name, b.normalized_name, b.category, d.domain, "
                "d.verification_source, d.verified_at FROM brands b "
                "LEFT JOIN official_domains d ON b.id = d.brand_id "
                "ORDER BY b.normalized_name, d.domain"
            ).fetchall()
            aliases = reviewed_aliases(conn, backend)
        entries = tuple(
            BrandDomain(name, category, domain if source and reviewed else None, source,
                        str(reviewed) if reviewed else None, tuple(aliases.get(key, ())))
            for name, key, category, domain, source, reviewed in rows
        )
        managed = {key for _, key, *_ in rows}
        return entries + tuple(b for b in STATIC_CATALOG if brand_key(b.name) not in managed), backend
    except Exception as error:
        # Driver exceptions can contain a host or credentials. Log only the type.
        LOGGER.debug("Catalog unavailable (%s)", type(error).__name__)
        return STATIC_CATALOG, "unavailable_static_fallback"


def load_reviewed_examples():
    """Read curated test fixtures. Fail visibly if the configured test store is unavailable."""
    with catalog_connection() as (conn, _):
        return conn.execute(
            "SELECT message_text, expected_label, scenario_type FROM scam_examples "
            "WHERE reviewed = TRUE ORDER BY scenario_type"
        ).fetchall()


def initialize_sqlite(path):
    """Seed a local database in one transaction. Existing team rows take precedence."""
    examples = json.loads((ROOT / "regression_cases.json").read_text(encoding="utf-8"))
    with closing(sqlite3.connect(path, timeout=5)) as conn, conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript("BEGIN IMMEDIATE;\n" + (ROOT / "schema.sql").read_text(encoding="utf-8"))
        for name, category, domain, source in REVIEWED_DOMAINS:
            key = brand_key(name)
            conn.execute(
                "INSERT INTO brands (name, normalized_name, category) VALUES (?, ?, ?) "
                "ON CONFLICT(normalized_name) DO NOTHING", (name, key, category)
            )
            conn.execute(
                "INSERT INTO official_domains (brand_id, domain, verification_source, verified_at) "
                "SELECT id, ?, ?, ? FROM brands WHERE normalized_name = ? "
                "ON CONFLICT(domain) DO NOTHING", (domain, source, "2026-11-06", key)
            )
        conn.executemany(
            "INSERT INTO scam_examples (message_text, expected_label, scenario_type, reviewed) "
            "VALUES (?, ?, ?, TRUE) ON CONFLICT(scenario_type) DO NOTHING",
            ((case["message"], case["label"], case["id"]) for case in examples)
        )


if __name__ == "__main__":
    path = Path(os.environ.get("AXA_SQLITE_PATH") or DEFAULT_DB).expanduser()
    initialize_sqlite(path)
    print(f"Catalog SQLite pregatit: {path}")
