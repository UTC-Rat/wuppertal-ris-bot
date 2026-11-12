import os
import requests

DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID")
OPARL_SYSTEM_URL = "https://oparl.wuppertal.de/oparl/system"

def main():
    print(f"DEBUG: DIFY_API_KEY vorhanden? -> {bool(DIFY_API_KEY)}")
    print(f"DEBUG: DIFY_DATASET_ID vorhanden? -> {bool(DIFY_DATASET_ID)}")

    if not DIFY_API_KEY or not DIFY_DATASET_ID:
        print("FEHLER: GitHub-Secrets DIFY_API_KEY oder DIFY_DATASET_ID fehlen!")
        return

    # 1. System-Daten abrufen, um an den Body (Körperschaft) zu gelangen
    print(f"Frage OParl-System ab: {OPARL_SYSTEM_URL} ...")
    try:
        res = requests.get(OPARL_SYSTEM_URL, timeout=15)
        res.raise_for_status()
        system_data = res.json()
        
        # OParl verlinkt in 'body' auf eine Liste oder direkte URL der Körperschaften
        bodies_link = system_data.get("body")
        if not bodies_link:
            # Manchmal ist es direkt eine Liste
            print("Kein direkter Body-Link im System gefunden, versuche Standard-Fallback...")
            body_url = "https://oparl.wuppertal.de/oparl/body"
        else:
            if isinstance(bodies_link, list) and len(bodies_link) > 0:
                body_url = bodies_link[0]
            elif isinstance(bodies_link, str):
                body_url = bodies_link
            else:
                body_url = "https://oparl.wuppertal.de/oparl/body"

        print(nutze_body_url := f"Verwende Body-URL: {body_url}")
        
    except Exception as e:
        print(f"Fehler beim Abruf des OParl-Systems: {e}")
        return

    # 2. Body-Daten abrufen, um die Papiere (Papers) zu finden
    try:
        res_body = requests.get(body_url, timeout=15)
        res_body.raise_for_status()
        body_data = res_body.json()
        
        # Manchmal ist body_data ein einzelnes Objekt oder eine Liste von Objekten
        if isinstance(body_data, list):
            body_obj = body_data[0]
        else:
            body_obj = body_data
            
        paper_url = body_obj.get("paper")
        
        # Wenn kein direkter Paper-Link im Body steht, nutzen wir den bekannten Standard-Pfad relativ zum Body
        if not paper_url:
            paper_url = body_url.rstrip("/") + "/paper"
            
        print(f"Hole Dokumente von: {paper_url}")
        
        res_papers = requests.get(paper_url, timeout=15)
        res_papers.raise_for_status()
        papers_data = res_papers.json()
        
        papers = papers_data.get("data", [])
        print(f"Erfolgreich {len(papers)} Dokumente aus Wuppertal geladen.")
        
    except Exception as e:
        print(f"Fehler beim Laden der Dokumente: {e}")
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
