import os
import requests

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID")

def main():
    print(f"DEBUG: DIFY_API_KEY vorhanden? -> {bool(DIFY_API_KEY)}")
    print(f"DEBUG: DIFY_DATASET_ID vorhanden? -> {bool(DIFY_DATASET_ID)}")

    if not DIFY_API_KEY or not DIFY_DATASET_ID:
        print("FEHLER: GitHub-Secrets DIFY_API_KEY oder DIFY_DATASET_ID fehlen!")
        return

    try:
        # 1. System abfragen
        system_url = "https://oparl.wuppertal.de/oparl/system"
        print(f"Frage OParl-System ab: {system_url}")
        res = requests.get(system_url, timeout=15)
        res.raise_for_status()
        sys_data = res.json()
        
        bodies_endpoint = sys_data.get("body")
        if isinstance(bodies_endpoint, list):
            bodies_url = bodies_endpoint[0]
        else:
            bodies_url = bodies_endpoint
        
        print(f"Bodies-URL: {bodies_url}")

        # 2. Body-Liste abfragen (Wuppertals Körperschaften)
        res_bodies = requests.get(bodies_url, timeout=15)
        res_bodies.raise_for_status()
        bodies_data = res_bodies.json()
        
        # OParl liefert Sammlungen oft in einem 'data'-Array oder als direkte Liste
        bodies_list = bodies_data.get("data", bodies_data)
        if isinstance(bodies_list, list) and len(bodies_list) > 0:
            body_obj = bodies_list[0]
        else:
            body_obj = bodies_list

        # Jetzt den Papier-Link aus dem konkreten Body auslesen
        paper_url = body_obj.get("paper")
        print(f"Ermittelter Papier-Endpunkt: {paper_url}")

        if not paper_url:
            # Fallback falls direkt nicht enthalten
            paper_url = "https://oparl.wuppertal.de/oparl/body/1/paper"
            print(f"Verwende Fallback-Papier-URL: {paper_url}")

        # 3. Papiere laden
        res_papers = requests.get(paper_url, timeout=15)
        res_papers.raise_for_status()
        papers_data = res_papers.json()
        
        papers = papers_data.get("data", [])
        print(f"Erfolgreich {len(papers)} Dokumente aus Wuppertal geladen!")

    except Exception as e:
        print(f"Fehler beim Abruf: {e}")
        return

    # 4. Dokumente an Dify übergeben
    for paper in papers[:10]:
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
            print(f"Übertrage '{name[:30]}...' -> Dify Status: {response.status_code}")
            if response.status_code not in [200, 201]:
                print(f"  Antwort-Details: {response.text}")
        except Exception as e:
            print(f"  Fehler bei Übertragung an Dify: {e}")

if __name__ == "__main__":
    main()
