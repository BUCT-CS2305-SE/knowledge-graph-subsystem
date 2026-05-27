from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

USER_AGENT = "Mozilla/5.0 (compatible; KG-Crawler/1.0; +https://example.org)"

MUSEUMS = [
    {
        "id": "met_museum",
        "name": "The Metropolitan Museum of Art",
        "start_url": "https://www.metmuseum.org/",
    },
    {
        "id": "guimet_museum",
        "name": "Musée Guimet",
        "start_url": "https://www.guimet.fr/en/collections/",
    },
    {
        "id": "british_museum",
        "name": "The British Museum",
        "start_url": "https://www.britishmuseum.org/collection/search?place=China",
    },
    {
        "id": "brooklyn_botanic",
        "name": "Brooklyn Botanic Garden",
        "start_url": "https://www.bbg.org/",
    },
]
