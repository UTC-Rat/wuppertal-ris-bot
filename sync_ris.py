import os
import json
import time
import requests

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID")
SYNCED_FILE = "synced_ids.json"

def load_synced_ids():
    """Lädt die Liste der bereits synchronisierten Dokument-IDs."""
    if os.path.exists(SYNCED_FILE):
        try:
            with open(SYNCED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_synced_ids(synced_set):
    """Speichert die Liste der synchronisierten Dokument-IDs ab."""
    try:
        with open(SYNCED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(synced_set), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Fehler beim Speichern der Sync-Liste: {e}")

def main():
    print(f"DEBUG: DIFY_API_KEY vorhanden? -> {bool(DIFY_API_KEY)}")
    print(f"DEBUG: DIFY_DATASET_ID vorhanden? -> {bool(DIFY_DATASET_ID)}")

    if not DIFY_API_KEY or not DIFY_DATASET_ID:
        print("FEHLER: GitHub-Secrets DIFY_API_KEY oder DIFY_DATASET_ID fehlen!")
        return

    synced_ids = load_synced_ids()
    print(f"Bereits im System registrierte Dokumente: {len(synced_ids)}")

    try:
        # 1. System abfragen
        system_url = "https://oparl.wuppertal.de/oparl/system"
        res = requests.get(system_url, timeout=15)
        res.raise_for_status()
        sys_data = res.json()
        
        bodies_endpoint = sys_data.get("body")
        bodies_url = bodies_endpoint[0] if isinstance(bodies_endpoint, list) else bodies_endpoint
        
        # 2. Body-Liste abfragen
        res_bodies = requests.get(bodies_url, timeout=15)
        res_bodies.raise_for_status()
        bodies_data = res_bodies.json()
        
        bodies_list = bodies_data.get("data", bodies_data)
        body_obj = bodies_list[0] if isinstance(bodies_list, list) and len(bodies_list) > 0 else bodies_list

        paper_url = body_obj.get("paper")
        if not paper_url:
            paper_url = "https://oparl.wuppertal.de/oparl/body/1/paper"

        # 3. Alle verfügbaren Papiere von Wuppertal laden
        res_papers = requests.get(paper_url, timeout=15)
        res_papers.raise_for_status()
        papers_data = res_papers.json()
        
        papers = papers_data.get("data", [])
        print(f"Gesamtanzahl gefundener Dokumente in Wuppertal: {len(papers)}")

    except Exception as e:
        print(f"Fehler beim Abruf der OParl-Daten: {e}")
        return

    # Filtern nach Dokumenten, die noch NICHT synchronisiert wurden
    new_papers = []
    for paper in papers:
        paper_id = paper.get("id") or paper.get("url")
        if paper_id and paper_id not in synced_ids:
            new_papers.append(paper)

    print(f"Noch nicht synchronisierte Dokumente in dieser Charge: {len(new_papers)}")

    # Wir nehmen pro Lauf maximal 5 Stück
    batch_to_sync = new_papers[:5]
    
    if not batch_to_sync:
        print("Keine neuen Dokumente zum Synchronisieren gefunden. Alles ist aktuell!")
        return

    success_count = 0
    for index, paper in enumerate(batch_to_sync):
        paper_id = paper.get("id") or paper.get("url")
        name = paper.get("name", "Dokument Wuppertal RIS")
        paper_type = paper.get("paperType", "Beschluss/Antrag")
        date = paper.get("date", "Datum unbekannt")
        web = paper.get("web", "")

        text_content = f"WUPPERTAL RIS DOKUMENT\n\nTitel: {name}\nTyp: {paper_type}\nDatum: {date}\nURL: {web}"

        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "name": f"{date} - {name[:40]}",
            "text": text_content,
            "indexing_technique": "high_quality",
            "process_rule": {"mode": "automatic"}
        }

        dify_url = f"https://api.dify.ai/v1/datasets/{DIFY_DATASET_ID}/document/create-by-text"
        
        try:
            response = requests.post(dify_url, headers=headers, json=payload, timeout=15)
            print(f"[{index+1}/{len(batch_to_sync)}] Übertrage '{name[:30]}...' -> Dify Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                synced_ids.add(paper_id)
                success_count += 1
            else:
                print(f"  Antwort-Details: {response.text}")
                if response.status_code == 403:
                    print("Rate-Limit erreicht. Stoppe diesen Durchlauf.")
                    break
        except Exception as e:
            print(f"  Fehler bei Übertragung an Dify: {e}")

        time.sleep(6)

    # Speichern der aktualisierten ID-Liste
    save_synced_ids(synced_ids)
    print(f"Sync-Durchlauf beendet. Erfolgreich übertragen: {success_count} Dokumente.")

if __name__ == "__main__":
    main()
