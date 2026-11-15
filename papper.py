"""
Pappersspel: boten "spelar" med låtsaspengar och rättar själv efter loppen.
Allt sparas i data/papperspel.csv så du kan se om boten tjänar pengar över tid.
"""
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import config
from atg_api import ATGKlient

KOLUMNER = ["id", "skapad", "spel_id", "lopp_id", "typ", "val", "insats", "odds", "chans",
            "status", "utbetalning", "kommentar"]


class Papperskassa:
    def __init__(self, data_dir="data"):
        self.fil = Path(data_dir) / "papperspel.csv"
        self.data_dir = data_dir
        self.df = pd.read_csv(self.fil, dtype={"val": str}) if self.fil.exists() else pd.DataFrame(columns=KOLUMNER)

    def spara(self):
        self.fil.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(self.fil, index=False)

    def bankrulle(self):
        d = self.df
        if d.empty:
            return float(config.BANKRULLE_START)
        rattade = d[d.status != "öppen"]
        return float(config.BANKRULLE_START + (rattade.utbetalning.sum() - rattade.insats.sum())
                     - d[d.status == "öppen"].insats.sum())

    def forlust_senaste_veckan(self):
        d = self.df[self.df.status != "öppen"]
        if d.empty:
            return 0.0
        ny = pd.to_datetime(d.skapad) >= datetime.now() - timedelta(days=7)
        return float(d[ny].insats.sum() - d[ny].utbetalning.sum())

    def finns(self, spel_id, typ, val):
        d = self.df
        return not d[(d.spel_id == spel_id) & (d.typ == typ) & (d.val.astype(str) == str(val))].empty

    def lagg(self, spel_id, lopp_id, typ, val, insats, odds=None, chans=None, kommentar=""):
        if insats <= 0 or self.finns(spel_id, typ, val):
            return False
        rad = {"id": len(self.df) + 1, "skapad": datetime.now().isoformat(timespec="minutes"),
               "spel_id": spel_id, "lopp_id": lopp_id, "typ": typ, "val": str(val), "insats": insats,
               "odds": odds, "chans": chans, "status": "öppen", "utbetalning": 0.0, "kommentar": kommentar}
        self.df = pd.concat([self.df, pd.DataFrame([rad])], ignore_index=True)
        return True

    # ---------- rättning ----------
    def ratta(self, offline=False):
        klient = ATGKlient(self.data_dir, offline=offline)
        antal = 0
        for idx, r in self.df[self.df.status == "öppen"].iterrows():
            spel = klient.spel(r.spel_id, farsk=True)
            if not spel or spel.get("status") != "results":
                continue
            utb = rattning(spel, r)
            if utb is None:
                self.df.loc[idx, "status"] = "okänd"
                continue
            self.df.loc[idx, ["status", "utbetalning"]] = ["vunnen" if utb > 0 else "förlorad", round(utb, 2)]
            antal += 1
        self.spara()
        return antal

    def sammanfattning(self):
        d = self.df
        if d.empty:
            return "Inga pappersspel ännu. Kör: python bot.py tips --spara"
        rad = [f"Bankrulle nu: {self.bankrulle():.0f} kr (start {config.BANKRULLE_START} kr)"]
        r = d[d.status.isin(["vunnen", "förlorad"])]
        if not r.empty:
            for typ, gr in r.groupby("typ"):
                ins, ut = gr.insats.sum(), gr.utbetalning.sum()
                rad.append(f"  {typ:10s} {len(gr):4d} spel  insats {ins:8.0f}  tillbaka {ut:8.0f}  "
                           f"ROI {(ut-ins)/ins*100:+6.1f} %  träffar {(gr.status=='vunnen').mean()*100:.0f} %")
            ins, ut = r.insats.sum(), r.utbetalning.sum()
            rad.append(f"  {'TOTALT':10s} {len(r):4d} spel  insats {ins:8.0f}  tillbaka {ut:8.0f}  ROI {(ut-ins)/ins*100:+6.1f} %")
        rad.append(f"Öppna spel: {(d.status=='öppen').sum()}")
        if len(r) < 200:
            rad.append("OBS: under 200 rättade spel säger resultatet nästan ingenting – slumpen dominerar.")
        return "\n".join(rad)


def _lopp_pool(spel, lopp_id, typ):
    for lopp in spel.get("races", []):
        if lopp["id"] == lopp_id:
            return (lopp.get("pools") or {}).get(typ, {}), lopp
    return {}, None


def rattning(spel, r):
    """Returnerar utbetalning i kr (0 om förlust) eller None om det inte gick att avgöra."""
    typ = r.typ
    if typ in ("Vinnare", "Plats", "Trio", "Tvilling"):
        pool, _ = _lopp_pool(spel, r.lopp_id, typ.lower())
        res = pool.get("result", {}) or {}
        vinnare = res.get("winners")
        if vinnare is None:
            return None
        if typ == "Vinnare":
            for w in vinnare:
                if str(w["number"]) == str(r.val):
                    return r.insats * w["odds"] / 100
            return 0.0
        if typ == "Plats":
            for lista in vinnare.values():
                for w in lista:
                    if str(w["number"]) == str(r.val):
                        return r.insats * w["odds"] / 100
            return 0.0
        mitt = [int(x) for x in str(r.val).split("-")]
        for w in vinnare:
            k = list(w["combination"])
            if (typ == "Trio" and k == mitt) or (typ == "Tvilling" and sorted(k) == sorted(mitt)):
                return r.insats * w["odds"] / 100
        return 0.0
    # Systemspel: val = "1,4/7/2,3/..."  (avdelningar separerade med /)
    pool = (spel.get("pools") or {}).get(typ, {})
    utd = (pool.get("result") or {}).get("payouts") or {}
    avd = [set(int(x) for x in a.split(",")) for a in str(r.val).split("/")]
    traff_per_avd = []
    for lopp, valda in zip(spel.get("races", []), avd):
        vinnare = {s["number"] for s in lopp.get("starts", []) if (s.get("result") or {}).get("place") == 1}
        traff_per_avd.append((len(valda & vinnare), len(valda)))
    # Räkna hur många rader som har exakt m rätt (polynom-trick)
    poly = np.array([1.0])
    for traff, antal in traff_per_avd:
        poly = np.convolve(poly, np.array([antal - traff, traff]))
    radpris = config.RADPRIS.get(typ, 1.0)
    rader = max(int(np.prod([a for _, a in traff_per_avd])), 1)
    skala = r.insats / (radpris * rader)        # 1.0 om du spelat fullt radpris
    summa = 0.0
    for m_str, info in utd.items():
        m = int(m_str)
        if m < len(poly) and poly[m] > 0:
            per_rad = (info.get("payout", 0) if isinstance(info, dict) else 0) / 100   # öre -> kr
            summa += poly[m] * per_rad * skala
    return summa
