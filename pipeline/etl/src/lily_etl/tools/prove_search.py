"""Step-2 proof, run as an in-cluster Job (the OpenSearch domain is VPC-only).

Takes the PARSED symptoms (the parser's real output from the repair-index
fixture) as JSON in LILY_SYMPTOMS_JSON, then: upsert → embed with Titan v2 →
index → hybrid BM25+kNN query, printing the actual top results. Uses the same
indexer (skip-unchanged) and query DSL the retrieval service will use.

    python -m lily_etl.tools.prove_search "ice maker not working"
"""

from __future__ import annotations

import json
import os
import sys

import boto3
import psycopg

from lily_etl.indexer import index_entity, load_symptom
from lily_etl.upsert import upsert_symptom_index
from lily_parsers.dto import ParsedSymptomIndex, SymptomRef
from lily_search.client import ensure_index, opensearch_client
from lily_search.embeddings import embed_text
from lily_search.index import hybrid_query, index_name, retrieval_mapping


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "ice maker not working"
    region = os.environ.get("AWS_REGION", "us-east-1")
    endpoint = os.environ["LILY_OPENSEARCH_ENDPOINT"]
    dsn = os.environ["LILY_DATABASE_URL"]
    parsed = json.loads(os.environ["LILY_SYMPTOMS_JSON"])

    index = ParsedSymptomIndex(
        appliance_type=parsed["appliance_type"],
        symptoms=[
            SymptomRef(
                name=s["name"],
                url=s["url"],
                reported_by_pct=s["pct"],
                description=s["description"],
            )
            for s in parsed["symptoms"]
        ],
    )

    bedrock = boto3.client("bedrock-runtime", region_name=region)
    os_client = opensearch_client(endpoint, region=region)
    created = ensure_index(os_client, index_name("symptoms"), retrieval_mapping())
    print(f"index {index_name('symptoms')} {'created' if created else 'exists'}", flush=True)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingestion.source_pages (url, page_type, parse_status, discovered_at) "
                "VALUES (%s,'category','parsed',now()) "
                "ON CONFLICT (url) DO UPDATE SET parse_status='parsed' RETURNING source_page_id",
                ("https://www.partselect.com/Repair/Refrigerator/",),
            )
            spid_row = cur.fetchone()
            assert spid_row is not None
            spid = spid_row[0]
        upsert_symptom_index(
            conn, index, source_url="https://www.partselect.com", source_page_id=spid
        )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT symptom_id FROM catalog.symptoms ORDER BY symptom_id")
            ids = [r[0] for r in cur.fetchall()]
        indexed = sum(
            1
            for sid in ids
            if (doc := load_symptom(conn, sid)) and index_entity(conn, os_client, bedrock, doc)
        )
        print(f"embedded + indexed {indexed} symptoms ({len(ids)} total)", flush=True)

    qvec = embed_text(bedrock, query)
    body = hybrid_query(text=query, vector=qvec, k=10, size=5, appliance_type="refrigerator")
    res = os_client.search(index=index_name("symptoms"), body=body)

    print(f"\nHYBRID SEARCH — query: {query!r}\n", flush=True)
    for i, hit in enumerate(res["hits"]["hits"], 1):
        src = hit["_source"]
        print(f"{i}. [{hit['_score']:.3f}] {src['title']}")
        print(f"     {src['body'][:90]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
