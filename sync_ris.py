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

    # 1. Start beim offiziellen Einstiegspunkt von Wuppertal
    system_url = "https://oparl.wuppertal.de/oparl/system"
    print(f"Frage Wuppertaler OParl-System ab: {system_url}")

    try:
        res = requests.get(system_url, timeout=15)
        res.raise_for_status()
        sys_data = res.json()
        
        # Holen der Body-URL aus dem System (z. B. "https://oparl.wuppertal.de/oparl/body/...")
        body_url = sys_data.get("body")
        if isinstance(body_url, list):
            body_url = body_url[0]
            
        print(f"Gefundene Body-URL: {body_url}")
        
        # Body abfragen, um den exakten 'paper'-Link zu bekommen
        res_body = requests.get(body_url, timeout=15)
        res_body.raise_for_status()
        body_data = res_body.json()
        
        # Wuppertal liefert hier den exakten Pfad für Papiere
        paper_url = body_data.get("paper")
        print(f"Exakter Papier-Endpunkt ermittelt: {paper_url}")
        
        # 2. Papiere/Dokumente abrufen
        res_papers = requests.get(paper_url, timeout=15)
        res_papers.raise_for_status()
        papers_data = res_papers.json()
        
        papers = papers_data.get("data", [])
        print(f"Erfolgreich {len(papers)} Dokumente aus Wuppertal geladen!")

    except Exception as e:
        print(f"Fehler beim dynamischen Abruf der OParl-Daten: {e}")
        return

    # 3. Dokumente an Dify übergeben
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
                print(f"  Antwort-Details von Dify: {response.text}")
        except Exception as e:
            print(f"  Fehler bei Übertragung an Dify: {e}")

if __name__ == "__main__":
    main()
