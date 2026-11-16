"""
Hämtar data från ATG:s öppna JSON-tjänst (samma data som atg.se visar).
Allt sparas i data/raw/ så att varje sida bara hämtas en gång.
"""
import json
import time
from datetime import date
from pathlib import Path

import requests

import config

BAS_URL = "https://www.atg.se/services/racinginfo/v1/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (privat ATG-bot for egen analys)", "Accept": "application/json"}


class ATGKlient:
    def __init__(self, data_dir="data", offline=False):
        self.raw = Path(data_dir) / "raw"
        self.offline = offline
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ---------- intern hjälp ----------
    def _las(self, fil):
        try:
            return json.loads(fil.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _hamta(self, url, fil):
        if self.offline:
            return None
        for forsok in range(3):
            try:
                r = self.session.get(url, timeout=30)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                data = r.json()
                fil.parent.mkdir(parents=True, exist_ok=True)
                fil.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                time.sleep(config.PAUS_MELLAN_ANROP)
                return data
            except requests.RequestException as e:
                print(f"  (nätverksfel, försöker igen: {e})")
                time.sleep(2 + forsok * 3)
        return None

    # ---------- publika funktioner ----------
    def kalender(self, dag):
        """Alla banor, lopp och spel en viss dag. dag = 'ÅÅÅÅ-MM-DD'."""
        fil = self.raw / "kalender" / f"{dag}.json"
        cache = self._las(fil) if fil.exists() else None
        # Gamla dagar ändras inte – använd sparad kopia. Idag/framåt: hämta nytt.
        if cache is not None and (dag < date.today().isoformat() or self.offline):
            return cache
        return self._hamta(f"{BAS_URL}/calendar/day/{dag}", fil) or cache

    def spel(self, spel_id, farsk=False):
        """Ett spel (t.ex. 'V85_2026-11-14_14_5' eller 'vinnare_2026-11-14_14_1')."""
        fil = self.raw / "spel" / f"{spel_id}.json"
        cache = self._las(fil) if fil.exists() else None
        if cache is not None and not farsk and cache.get("status") == "results":
            return cache                       # färdigt spel ändras aldrig
        if cache is not None and self.offline:
            return cache
        return self._hamta(f"{BAS_URL}/games/{spel_id}", fil) or cache


    def hast_resultat(self, hast_id, max_timmar=12):
        """Hästens tidigare lopp (datum, placering, km-tid, odds, galopp ...). Hämtas om max 2 ggr/dag."""
        fil = self.raw / "hastar" / f"{hast_id}.json"
        if fil.exists() and (self.offline or time.time() - fil.stat().st_mtime < max_timmar * 3600):
            return self._las(fil)
        return self._hamta(f"{BAS_URL}/horses/{hast_id}/results", fil) or (self._las(fil) if fil.exists() else None)

    def kommentarer(self, lopp_id):
        """ATG:s korta spelkommentar per startnummer, t.ex. '3 segrar på 4 starter på banan'."""
        fil = self.raw / "kommentarer" / f"{lopp_id}.json"
        if fil.exists():
            return self._las(fil)
        return self._hamta(f"{BAS_URL}/races/{lopp_id}/comments", fil)


def spel_i_kalender(kal, typer=None):
    """Lista spel i en kalender: [{'typ','id','status','races','startTime', ...}]"""
    ut = []
    if not kal:
        return ut
    banor = {t["id"]: t for t in kal.get("tracks", [])}
    for typ, lista in (kal.get("games") or {}).items():
        if typer and typ not in typer:
            continue
        for g in lista:
            if not isinstance(g, dict) or not g.get("id"):
                continue                       # framtida dagar kan ha spel utan id än
            bana_ids = g.get("tracks") or []
            bana = banor.get(bana_ids[0]) if bana_ids else None
            ut.append({**g, "typ": typ,
                       "bana": bana.get("name") if bana else "?",
                       "land": bana.get("countryCode") if bana else "?",
                       "sport": bana.get("sport") if bana else "?"})
    return ut


def lopp_i_kalender(kal):
    """Alla lopp en dag som matchar LANDER och SPORT i config."""
    ut = []
    if not kal:
        return ut
    for t in kal.get("tracks", []):
        if t.get("countryCode") not in config.LANDER or t.get("sport") != config.SPORT:
            continue
        for r in t.get("races", []):
            ut.append({"lopp_id": r["id"], "status": r.get("status"), "bana": t["name"],
                       "nr": r.get("number"), "starttid": r.get("startTime")})
    return ut
