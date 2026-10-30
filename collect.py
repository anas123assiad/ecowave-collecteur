#!/usr/bin/env python3
"""
Collecteur MASI — le gardien 24/7 (Pierre 5).
Tourne dans GitHub Actions toutes les 15 minutes :
  1. appelle le relais cours.php (cours différés, Bourse de Casablanca),
  2. range les cours dans Supabase (tables cours + cours_bruts),
  3. si le relais est en mode « indicatif » (source en panne), il ne
     range RIEN — on ne pollue pas l'historique avec des données datées.

Secrets requis (GitHub → Settings → Secrets → Actions) :
  SUPABASE_URL          ex. https://abcdefgh.supabase.co
  SUPABASE_SERVICE_KEY  clé service_role du projet Supabase
Aucun secret n'est écrit dans ce fichier.
"""

import json
import os
import sys
import urllib.request

RELAY_URL = "https://agadirecowave.com/unifiee/api/cours.php"


def http_json(url, data=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body.strip() else None


def post_rows(table, rows, supabase_url, service_key):
    if not rows:
        return
    url = f"{supabase_url}/rest/v1/{table}"
    payload = json.dumps(rows).encode("utf-8")
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        # ignore-duplicates = l'équivalent PostgREST de ON CONFLICT DO NOTHING
        "Prefer": "resolution=ignore-duplicates,return=minimal",
    }
    http_json(url, data=payload, headers=headers)
    print(f"{table}: {len(rows)} ligne(s) envoyée(s)")


def main():
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_KEY"]

    data = http_json(RELAY_URL, headers={"User-Agent": "CollecteurMASI/1.0"})
    quote_ts = data.get("updated_at")

    if data.get("indicatif"):
        print(f"Relais en mode INDICATIF (données du {quote_ts}) — rien rangé.")
        return

    quotes = data.get("quotes") or {}
    rows = [
        {
            "symbole": sym,
            "prix": q.get("price"),
            "variation": q.get("var"),
            "quote_ts": quote_ts,
        }
        for sym, q in quotes.items()
        if q.get("price") is not None
    ]
    post_rows("cours", rows, supabase_url, service_key)

    tape = data.get("tape") or []
    raw_rows = [
        {
            "nom": t.get("name"),
            "prix": t.get("price"),
            "var_abs": t.get("var_abs"),
            "quote_ts": quote_ts,
        }
        for t in tape
        if t.get("name") and t.get("price") is not None
    ]
    post_rows("cours_bruts", raw_rows, supabase_url, service_key)

    print(f"OK — cours du {quote_ts} rangés.")


if __name__ == "__main__":
    sys.exit(main())
