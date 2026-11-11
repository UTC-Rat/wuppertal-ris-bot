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

    # Direkter OParl-Papier-Endpunkt der Stadt Wuppertal
    paper_url = "https://oparl.wuppertal.de/oparl/bodies/0/paper"
    print(f"Hole Dokumente direkt von: {paper_url} ...")
    
    try:
        res = requests.get(paper_url, timeout=15)
        res.raise_for_status()
        data = res.json()
        papers = data.get("data", [])
        print(f"Erfolgreich {len(papers)} Dokumente aus Wuppertal geladen.")
    except Exception as e:
        print(f"Fehler beim Abruf der OParl-Daten: {e}")
        return

    # Die neuesten Dokumente an Dify übergeben
    for paper in papers[:10]:
        name = paper.get("name", "Dokument Wuppertal RIS")
        paper_type = paper.get("paperType", "Beschluss/Antrag")
        date = paper.get("date", "Datum unbefannt")
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
