import os
import requests
import json

# Konfiguration
OPARL_SYSTEM_URL = "https://oparl.wuppertal.de/oparl/system"

# Zugangsdaten für die Cloud-KI aus den GitHub-Umgebungsvariablen lesen
DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID")

def get_latest_papers():
    """Holt die neuesten Dokumente/Anträge aus der Wuppertaler OParl-API."""
    print("Verbinde mit dem Wuppertaler Ratsinformationssystem...")
    
    try:
        # System-Einstiegspunkt abrufen
        sys_res = requests.get(OPARL_SYSTEM_URL).json()
        body_url = sys_res["body"][0]
        
        # Dokumente (Papers) abrufen
        papers_url = f"{body_url}/paper"
        papers_res = requests.get(papers_url).json()
        
        # Gibt die Liste der aktuellsten Dokumente zurück
        return papers_res.get("data", [])
    except Exception as e:
        print(f"Fehler beim Abrufen der OParl-Daten: {e}")
        return []

def send_to_cloud_ai(paper):
    """Sendet ein einzelnes Dokument direkt in den Cloud-KI-Speicher."""
    title = paper.get("name", "Unbenanntes Dokument")
    paper_type = paper.get("paperType", "Dokument")
    date = paper.get("date", "Unbekanntes Datum")
    
    # Text-Inhalte und Links sammeln
    web_link = paper.get("web", "")
    main_file = paper.get("mainFile", {})
    file_url = main_file.get("accessUrl", "") if isinstance(main_file, dict) else ""

    text_content = f"Titel: {title}\nTyp: {paper_type}\nDatum: {date}\nLink zum RIS: {web_link}\nDatei-URL: {file_url}"

    # Beispiel-Anbindung an Dify.ai Knowledge Base via API
    if DIFY_API_KEY and DIFY_DATASET_ID:
        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "name": f"{date}_{title[:30]}",
            "text": text_content,
            "indexing_technique": "high_quality",
            "process_rule": {"mode": "automatic"}
        }
        api_url = f"https://api.dify.ai/v1/datasets/{DIFY_DATASET_ID}/document/create_by_text"
        
        response = requests.post(api_url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            print(f"Erfolgreich an Cloud-KI übertragen: {title}")
        else:
            print(f"Fehler beim Übertragen an Cloud-KI ({response.status_code}): {response.text}")
    else:
        print(f"[Simulation] Dokument erfasst: {title} (Keine Cloud-API-Schlüssel hinterlegt)")

def main():
    papers = get_latest_papers()
    print(f"{len(papers)} Dokumente gefunden.")
    
    for paper in papers[:10]:  # Verarbeitet die 10 aktuellsten Einträge
        send_to_cloud_ai(paper)

if __name__ == "__main__":
    main()
