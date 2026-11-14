import os
import json
import time
import requests
from datetime import datetime

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID")
SYNCED_FILE = "synced_ids.json"

# Wie viele Wuppertaler RIS-Einträge in EINE Dify-Datei gebündelt werden sollen
BUNDLE_SIZE = 50
# Wie viele Sammelpakete pro GitHub-Lauf maximal hochgeladen werden (3 Pakete = 150 Dokumente)
MAX_BUNDLES_PER_RUN = 3

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

def chunk_list(data, size):
    """Teilt eine Liste in gleich große Pakete auf."""
    for i in range(0, len(data), size):
        yield data[i:i + size]

def main():
    print(f"DEBUG: DIFY_API_KEY vorhanden? -> {bool(DIFY_API_KEY)}")
    print(f"DEBUG: DIFY_DATASET_ID vorhanden? -> {bool(DIFY_DATASET_ID)}")

    if not DIFY_API_KEY or not DIFY_DATASET_ID:
        print("FEHLER: GitHub-Secrets DIFY_API_KEY oder DIFY_DATASET_ID fehlen!")
        return

    synced_ids = load_synced_ids()
    print(f"Bereits im System registrierte Einzel-Dokumente: {len(synced_ids)}")

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

        # 3. Papiere von Wuppertal laden (inkl. Pagination für historische Tiefe)
        all_papers = []
        current_url = paper_url
        for _ in range(15):
            if not current_url:
                break
            res_papers = requests.get(current_url, timeout=15)
            res_papers.raise_for_status()
            papers_data = res_papers.json()
            all_papers.extend(papers_data.get("data", []))
            
            links = papers_data.get("links", {})
            current_url = links.get("next")

        print(f"Gesamtanzahl geprüfter Dokumente in Wuppertal: {len(all_papers)}")

    except Exception as e:
        print(f"Fehler beim Abruf der OParl-Daten: {e}")
        return

    # Filtern nach Dokumenten, die noch NICHT synchronisiert wurden
    new_papers = []
    for paper in all_papers:
        paper_id = paper.get("id") or paper.get("url")
        if paper_id and paper_id not in synced_ids:
            new_papers.append(paper)

    print(f"Noch nicht synchronisierte Einzel-Dokumente gefunden: {len(new_papers)}")

    if not new_papers:
        print("Keine neuen Dokumente zum Synchronisieren gefunden. Alles ist aktuell!")
        return

    # Aufteilen in Pakete zu je 50 Dokumenten
    bundles = list(chunk_list(new_papers, BUNDLE_SIZE))[:MAX_BUNDLES_PER_RUN]
    print(f"Erstelle {len(bundles)} Sammelpaket(e) mit je bis zu {BUNDLE_SIZE} Dokumenten...")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    total_synced_in_run = 0

    for b_idx, bundle in enumerate(bundles):
        entries_text = []
        bundle_ids = []
        dates_in_bundle = []

        for paper in bundle:
            paper_id = paper.get("id") or paper.get("url")
            name = paper.get("name", "Dokument Wuppertal RIS")
            paper_type = paper.get("paperType", "Beschluss/Antrag")
            date = paper.get("date", "Datum unbekannt")
            reference = paper.get("reference", "")
            web = paper.get("web", "")

            if date != "Datum unbekannt":
                dates_in_bundle.append(date)

            entry = (
                f"=== WUPPERTAL RIS DOKUMENT ===\n"
                f"Titel: {name}\n"
                f"Vorlagen-Nr.: {reference}\n"
                f"Typ: {paper_type}\n"
                f"Datum: {date}\n"
                f"Link: {web}\n"
            )
            entries_text.append(entry)
            bundle_ids.append(paper_id)

        combined_text = "\n\n".join(entries_text)
        
        date_range = ""
        if dates_in_bundle:
            dates_in_bundle.sort()
            date_range = f"({dates_in_bundle[0]} bis {dates_in_bundle[-1]})"

        bundle_name = f"Wuppertal_RIS_Paket_{timestamp}_Teil{b_idx+1}_{len(bundle)}Dok {date_range}"

        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "name": bundle_name,
            "text": combined_text,
            "indexing_technique": "economy",
            "process_rule": {
                "mode": "custom",
                "rules": {
                    "pre_processing_rules": [
                        {"id": "remove_extra_spaces", "enabled": True},
                        {"id": "remove_urls_emails", "enabled": False}
                    ],
                    "segmentation": {
                        "separator": "=== WUPPERTAL RIS DOKUMENT ===",
                        "max_tokens": 800
                    }
                }
            }
        }

        dify_url = f"https://api.dify.ai/v1/datasets/{DIFY_DATASET_ID}/document/create-by-text"

        try:
            response = requests.post(dify_url, headers=headers, json=payload, timeout=30)
            print(f"[Paket {b_idx+1}/{len(bundles)}] Übertrage '{bundle_name}' -> Dify Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                for pid in bundle_ids:
                    synced_ids.add(pid)
                total_synced_in_run += len(bundle_ids)
            else:
                print(f"  Antwort-Details: {response.text}")
                if response.status_code == 403:
                    print("Rate-Limit erreicht. Stoppe diesen Durchlauf.")
                    break
        except Exception as e:
            print(f"  Fehler bei Übertragung an Dify: {e}")

        time.sleep(5)

    save_synced_ids(synced_ids)
    print(f"Sync-Durchlauf beendet. Insgesamt {total_synced_in_run} Dokumente in {len(bundles)} Sammeldatei(en) gespeichert.")

if __name__ == "__main__":
    main()
