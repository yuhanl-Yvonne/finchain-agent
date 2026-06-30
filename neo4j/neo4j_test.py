from __future__ import annotations

import argparse
import getpass
import importlib
import os

GraphDatabase = importlib.import_module("neo4j").GraphDatabase


URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Neo4j connectivity and imported graph counts.")
    parser.add_argument(
        "--check-graph",
        action="store_true",
        help="Run post-import count queries for Company / ChainPosition / Region / RiskCase nodes.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    password = os.getenv("NEO4J_PASSWORD") or getpass.getpass("Neo4j password: ")
    driver = GraphDatabase.driver(URI, auth=(USERNAME, password))
    try:
        driver.verify_connectivity()
        print("Neo4j connected from Python")
        if args.check_graph:
            queries = {
                "Company": "MATCH (n:Company) RETURN count(n) AS cnt",
                "ChainPosition": "MATCH (n:ChainPosition) RETURN count(n) AS cnt",
                "Region": "MATCH (n:Region) RETURN count(n) AS cnt",
                "RiskCase": "MATCH (n:RiskCase) RETURN count(n) AS cnt",
                "BELONGS_TO_CHAIN": "MATCH (:Company)-[r:BELONGS_TO_CHAIN]->(:ChainPosition) RETURN count(r) AS cnt",
                "IN_REGION": "MATCH (:Company)-[r:IN_REGION]->(:Region) RETURN count(r) AS cnt",
                "HAS_RISK_EVENT": "MATCH (:Company)-[r:HAS_RISK_EVENT]->(:RiskCase) RETURN count(r) AS cnt",
            }
            with driver.session(database=DATABASE) as session:
                for label, query in queries.items():
                    cnt = session.run(query).single()["cnt"]
                    print(f"{label}: {cnt}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
