"""Neo4j AuraDB integration: offloads descriptor alias resolution, chronological
payment chains (NEXT_CHARGE), and payment-rail graph queries from Gemini & Python.
"""
import hashlib
import logging
from collections import Counter
from datetime import date
from neo4j import GraphDatabase
from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME

log = logging.getLogger(__name__)
_driver = None
_schema_ready = False


def get_driver():
    global _driver
    if not NEO4J_URI or not NEO4J_PASSWORD:
        return None
    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            connection_timeout=5,
        )
    return _driver


def ensure_schema():
    global _schema_ready
    driver = get_driver()
    if not driver or _schema_ready:
        return
    constraints = [
        "CREATE CONSTRAINT merchant_id IF NOT EXISTS FOR (m:Merchant) REQUIRE m.id IS UNIQUE",
        "CREATE CONSTRAINT descriptor_text IF NOT EXISTS FOR (d:RawDescriptor) REQUIRE d.text IS UNIQUE",
        "CREATE CONSTRAINT tx_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.tx_id IS UNIQUE",
        "CREATE CONSTRAINT rail_name IF NOT EXISTS FOR (r:PaymentRail) REQUIRE r.name IS UNIQUE",
    ]
    with driver.session() as session:
        for q in constraints:
            session.run(q)
    _schema_ready = True


def fetch_debits():
    """Read all debit Transaction nodes directly from Neo4j (replaces Supabase db.py)."""
    driver = get_driver()
    if not driver:
        raise RuntimeError("NEO4J_URI / NEO4J_PASSWORD not configured.")
    ensure_schema()
    with driver.session() as session:
        res = session.run("""
            MATCH (t:Transaction)
            WHERE t.date IS NOT NULL AND t.description IS NOT NULL AND t.amount IS NOT NULL
            RETURN t.tx_id AS id,
                   substring(toString(t.date), 0, 10) AS date,
                   t.description AS description,
                   toFloat(t.amount) AS amount
            ORDER BY date ASC, id ASC
        """)
        return [
            {"id": str(r["id"]), "date": r["date"], "description": r["description"], "amount": r["amount"]}
            for r in res
        ]


def upsert_raw_debits(rows, source_name="pdf_upload"):
    """Insert extracted bank statement debits into Neo4j without duplicating existing charges."""
    driver = get_driver()
    if not driver:
        raise RuntimeError("NEO4J_URI / NEO4J_PASSWORD not configured.")
    if not rows:
        return 0

    ensure_schema()
    seen_counts = Counter()
    payload = []

    for r in rows:
        tx_date = str(r["date"])[:10]
        desc = " ".join(str(r["description"]).split())
        amt = round(float(r["amount"]), 2)
        base_key = f"{tx_date}|{desc.upper()}|{amt:.2f}"
        occ = seen_counts[base_key]
        seen_counts[base_key] += 1

        digest = hashlib.sha256(f"{base_key}|{occ}".encode("utf-8")).hexdigest()[:16]
        payload.append({
            "tx_id": f"tx_{digest}",
            "date": tx_date,
            "description": desc,
            "amount": amt,
            "source_file": source_name,
        })

    cypher = """
    UNWIND $rows AS row
    MERGE (t:Transaction {tx_id: row.tx_id})
    ON CREATE SET t.date = row.date,
                  t.description = row.description,
                  t.amount = row.amount,
                  t.source_file = row.source_file
    """
    with driver.session() as session:
        session.run(cypher, rows=payload)

    log.info("Upserted %d debit transactions into Neo4j from %s.", len(payload), source_name)
    return len(payload)


def resolve_known_txs(txs):
    """Offload #1: Match transactions against known RawDescriptor -> Merchant aliases in Neo4j.
    Returns (known_llm_items, unknown_txs) so Gemini only processes unseen descriptors.
    """
    driver = get_driver()
    if not driver or not txs:
        return [], txs

    try:
        ensure_schema()
        rows = [{"id": t["id"], "text": t["description"].strip()} for t in txs]
        query = """
        UNWIND $rows AS row
        MATCH (d:RawDescriptor {text: row.text})-[:ALIAS_OF]->(m:Merchant)
        RETURN row.id AS tx_id,
               m.name AS name,
               m.frequency AS frequency,
               m.category AS category,
               m.payment_mechanism AS payment_mechanism,
               m.cancellation_steps AS cancellation_steps
        """
        grouped = {}
        matched_ids = set()
        with driver.session() as session:
            for rec in session.run(query, rows=rows):
                tx_id = rec["tx_id"]
                matched_ids.add(tx_id)
                key = rec["name"]
                if key not in grouped:
                    grouped[key] = {
                        "name": rec["name"],
                        "frequency": rec["frequency"],
                        "category": rec["category"],
                        "payment_mechanism": rec["payment_mechanism"] or "",
                        "cancellation_steps": list(rec["cancellation_steps"] or []),
                        "transaction_ids": [],
                    }
                grouped[key]["transaction_ids"].append(tx_id)

        unknown_txs = [t for t in txs if t["id"] not in matched_ids]
        log.info(
            "Neo4j resolved %d/%d transactions (%d unseen sent to Gemini).",
            len(matched_ids), len(txs), len(unknown_txs),
        )
        return list(grouped.values()), unknown_txs
    except Exception as exc:
        log.warning("Neo4j lookup skipped (falling back to full Gemini): %s", exc)
        return [], txs


def sync_commitments_to_graph(commitments, raw_txs):
    """Offload #2: Persist Merchant, RawDescriptor, PaymentRail, and chronological
    Transaction chains with precomputed day gaps and price deltas on NEXT_CHARGE edges.
    """
    driver = get_driver()
    if not driver or not commitments:
        return

    try:
        ensure_schema()
        tx_lookup = {(t["date"], t["description"], float(t["amount"])): t["id"] for t in raw_txs}

        payload = []
        for c in commitments:
            hist = c.get("history", [])
            tx_nodes = []
            for idx, h in enumerate(hist):
                tx_id = tx_lookup.get((h["date"], h["description"], float(h["amount"])), f"{c['id']}:{idx}")
                tx_nodes.append({
                    "tx_id": str(tx_id),
                    "date": h["date"],
                    "description": h["description"].strip(),
                    "amount": float(h["amount"]),
                })

            edges = []
            for prev, cur in zip(tx_nodes, tx_nodes[1:]):
                days_elapsed = (date.fromisoformat(cur["date"][:10]) - date.fromisoformat(prev["date"][:10])).days
                price_delta = round(cur["amount"] - prev["amount"], 2)
                pct_change = round((price_delta / prev["amount"]) * 100, 1) if prev["amount"] > 0 else 0.0
                edges.append({
                    "from_id": prev["tx_id"],
                    "to_id": cur["tx_id"],
                    "days_elapsed": days_elapsed,
                    "price_delta": price_delta,
                    "pct_change": pct_change,
                })

            payload.append({
                "id": c["id"],
                "name": c["name"],
                "frequency": c["frequency"],
                "category": c["category"],
                "latest_amount": float(c["amount"]),
                "payment_mechanism": c.get("payment_mechanism") or "Unknown",
                "cancellation_steps": c.get("cancellation_steps") or [],
                "tx_nodes": tx_nodes,
                "edges": edges,
            })

        cypher = """
        UNWIND $items AS item
        MERGE (m:Merchant {id: item.id})
        SET m.name = item.name,
            m.frequency = item.frequency,
            m.category = item.category,
            m.latest_amount = item.latest_amount,
            m.payment_mechanism = item.payment_mechanism,
            m.cancellation_steps = item.cancellation_steps

        MERGE (r:PaymentRail {name: item.payment_mechanism})
        MERGE (m)-[:BILLED_VIA]->(r)

        WITH item, m, r
        UNWIND item.tx_nodes AS tx
        MERGE (d:RawDescriptor {text: tx.description})
        MERGE (d)-[:ALIAS_OF]->(m)
        MERGE (t:Transaction {tx_id: tx.tx_id})
        SET t.date = tx.date, t.amount = tx.amount, t.description = tx.description
        MERGE (t)-[:PAID_TO]->(m)
        MERGE (t)-[:VIA_RAIL]->(r)

        WITH item
        UNWIND item.edges AS e
        MATCH (a:Transaction {tx_id: e.from_id}), (b:Transaction {tx_id: e.to_id})
        MERGE (a)-[rel:NEXT_CHARGE]->(b)
        SET rel.days_elapsed = e.days_elapsed,
            rel.price_delta = e.price_delta,
            rel.pct_change = e.pct_change
        """
        with driver.session() as session:
            session.run(cypher, items=payload)
        log.info("Synced %d commitments into Neo4j graph.", len(payload))
    except Exception as exc:
        log.warning("Neo4j graph sync failed: %s", exc)


def get_graph_insights():
    """Offload #3: Pure Cypher queries for dark patterns & multi-alias exposure."""
    driver = get_driver()
    if not driver:
        return {"connected": False, "price_hikes": [], "frequency_spikes": [], "rails": []}

    with driver.session() as session:
        hikes = [
            dict(r) for r in session.run("""
            MATCH (a:Transaction)-[rel:NEXT_CHARGE]->(b:Transaction)-[:PAID_TO]->(m:Merchant)
            WHERE rel.pct_change >= 5 OR (a.amount = 0 AND b.amount > 0)
            RETURN m.name AS merchant, a.amount AS from_amt, b.amount AS to_amt,
                   rel.pct_change AS pct_change, b.date AS date
            ORDER BY b.date DESC
            """)
        ]
        spikes = [
            dict(r) for r in session.run("""
            MATCH (a:Transaction)-[r1:NEXT_CHARGE]->(b:Transaction)-[r2:NEXT_CHARGE]->(c:Transaction)-[:PAID_TO]->(m:Merchant)
            WHERE r2.days_elapsed < 0.6 * r1.days_elapsed
            RETURN m.name AS merchant, r1.days_elapsed AS prev_gap_days,
                   r2.days_elapsed AS new_gap_days, c.date AS date
            ORDER BY c.date DESC
            """)
        ]
        rails = [
            dict(r) for r in session.run("""
            MATCH (m:Merchant)-[:BILLED_VIA]->(r:PaymentRail)
            RETURN r.name AS rail, collect(m.name) AS merchants,
                   round(sum(m.latest_amount)) AS latest_sum
            ORDER BY latest_sum DESC
            """)
        ]
    return {"connected": True, "price_hikes": hikes, "frequency_spikes": spikes, "rails": rails}
