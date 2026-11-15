"""
Analysmotorn: tar ett V-spel eller ett lopp och räknar fram botens förslag.
Används både av 'tips' (du kör själv) och 'automat' (GitHub kör var 10:e minut).
"""
import os
from datetime import datetime

import numpy as np
import pandas as pd

import json
import math

import requests

import config
import strategy
from features import rader_fran_spel
from model import marknads_p

SYSTEMNAMN = (("Försiktig", 0.3), ("Balanserad", 1.0), ("Skrällvänlig", 2.0))


_START = datetime.now()


def _fart():
    return float(os.environ.get("ATG_FART", "1"))


def nu():
    """Aktuell svensk tid. För test: ATG_NU='2026-11-16T18:10' (startklocka) och ATG_FART=30 (snabbspolning)."""
    if os.environ.get("ATG_NU"):
        return datetime.fromisoformat(os.environ["ATG_NU"]) + (datetime.now() - _START) * _fart()
    return datetime.now()


def sov(sekunder):
    """Vänta (i testläge snabbspolas väntan)."""
    import time
    time.sleep(max(sekunder, 0) / _fart())


def minuter_kvar(starttid):
    """Minuter tills start (negativt = har startat). starttid = '2026-11-16T18:20:00' (svensk tid)."""
    try:
        return (datetime.fromisoformat(str(starttid)[:19]) - nu()).total_seconds() / 60
    except ValueError:
        return None


def df_for_spel(spel, typ, klient=None, rorelse=None, ai=None):
    df = pd.DataFrame(rader_fran_spel(spel, typ, klient, rorelse, ai))
    if df.empty:
        return df
    return df.sort_values(["lopp_nr", "nr"]).reset_index(drop=True)


def analysera_system(klient, modell, g, budget, rorelse=None, ai=None):
    """V-spel -> dict med avdelningar och tre system. None om data saknas."""
    spel = klient.spel(g["id"], farsk=True)
    df = df_for_spel(spel, g["typ"], klient, rorelse, ai)
    if df.empty:
        return None
    odds_oppna = bool(pd.to_numeric(df["odds"], errors="coerce").notna().mean() > 0.5
                      and df["omsattning"].median() >= config.MIN_OMSATTNING)
    if not odds_oppna:
        df["odds"] = np.nan            # tidiga odds är brus – använd streck + egen analys
    df["p"] = modell.p_slutlig(df)
    avdrag = 1 - g["returnToPlayer"] / 100 if g.get("returnToPlayer") else config.AVDRAG.get(g["typ"], 0.35)
    radpris = config.RADPRIS.get(g["typ"], 1.0)
    avd, visning = [], []
    for i, (_, l) in enumerate(df.groupby("lopp_nr", sort=True), 1):
        l = l.sort_values("p", ascending=False)
        s = pd.to_numeric(l["streck"], errors="coerce").fillna(l["p"] * 100).values / 100
        s = np.maximum(s, 0.01)                       # tidiga streck kan vara 0 %
        s = 0.85 * s / s.sum() + 0.15 / len(s)        # jämna ut brus i tidiga streck
        avd.append((list(l["nr"]), list(l["p"]), list(s)))
        visning.append({"avd": i, "lopp_nr": int(l["lopp_nr"].iloc[0]), "spik": bool(l["p"].iloc[0] >= 0.45),
                        "hastar": [{"nr": int(n), "hast": h, "p": float(p), "streck": float(st)}
                                   for n, h, p, st in zip(l["nr"], l["hast"], l["p"], s)]})
    system = {}
    for namn, vikt in SYSTEMNAMN:
        sy = strategy.bygg_system(avd, budget, radpris, avdrag, vardevikt=vikt)
        sy["val"] = "/".join(",".join(str(n) for n in v) for v in sy["avdelningar"])
        sy["avdelningar"] = [[int(n) for n in v] for v in sy["avdelningar"]]
        system[namn] = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v) for k, v in sy.items()}
    # Jackpott: pengar från tidigare omgångar läggs ovanpå potten -> lägre krav på värdeindex
    jackpott = float(g.get("jackpotAmount") or (spel.get("pools", {}).get(g["typ"], {}) or {}).get("jackpotAmount") or 0)
    oms = float(((spel.get("pools", {}) or {}).get(g["typ"], {}) or {}).get("turnover") or 0) / 100
    netto = oms * (1 - avdrag)
    jp_faktor = min(1 + jackpott / netto, 3.0) if (jackpott and netto > 100000) else 1.0
    return {"id": g["id"], "typ": g["typ"], "bana": g["bana"], "start": g.get("startTime"),
            "avdrag": avdrag, "kravs": 1 / (1 - avdrag) / jp_faktor, "odds_oppna": odds_oppna,
            "jackpott": jackpott, "omsattning": oms, "jp_faktor": jp_faktor,
            "avdelningar": visning, "system": system}


def analysera_lopp(klient, modell, l, bank, rorelse=None, ai=None, spel=None):
    """Ett lopp -> dict med favoriter och värdespel (Vinnare, Plats, Trio, Tvilling + korspool)."""
    spel = spel or klient.spel(f"vinnare_{l['lopp_id']}", farsk=True)
    df = df_for_spel(spel, "vinnare", klient, rorelse, ai)
    if df.empty or pd.to_numeric(df["odds"], errors="coerce").isna().all():
        return None
    ut = {"lopp_id": l["lopp_id"], "bana": l["bana"], "nr": l["nr"], "start": l["starttid"],
          "omsattning": float(df["omsattning"].max() or 0), "for_lite_pengar": False, "favoriter": [], "spel": []}
    if ut["omsattning"] < config.MIN_OMSATTNING:
        ut["for_lite_pengar"] = True
        return ut
    p = modell.p_slutlig(df)
    lopp = df.to_dict("records")
    ordning = np.argsort(-p)
    ut["favoriter"] = [{"nr": int(lopp[i]["nr"]), "hast": lopp[i]["hast"], "p": float(p[i]),
                        "odds": float(lopp[i]["odds"]) if lopp[i]["odds"] else None,
                        "rorelse": float(lopp[i]["rorelse"]) if not lopp[i]["rorelse_saknas"] else None,
                        "ai": float(lopp[i]["ai_poang"]) if not lopp[i]["ai_saknas"] else None}
                       for i in ordning[:4]]
    # Störst marknadsrörelser (spelas ner = smarta pengar?)
    ut["rorelser"] = sorted([{"nr": int(r["nr"]), "hast": r["hast"], "rorelse": float(r["rorelse"])}
                             for r in lopp if not r["rorelse_saknas"] and abs(r["rorelse"]) >= 0.15],
                            key=lambda x: -x["rorelse"])[:3]
    pm = marknads_p(df).values
    for f in strategy.vinnare_plats(lopp, p, bank):
        if f["insats"] > 0:
            ut["spel"].append({"typ": f["typ"], "val": str(f["nr"]), "hast": f["hast"], "chans": float(f["chans"]),
                               "odds": float(f["odds"]), "overvarde": float(f["overvarde"]), "insats": f["insats"],
                               "spel_id": f"vinnare_{l['lopp_id']}"})
    for typ in ("trio", "tvilling"):
        ts = klient.spel(f"{typ}_{l['lopp_id']}", farsk=True)
        pool = (ts or {}).get("pools", {}).get(typ)
        for v in strategy.kombinationer(lopp, p, pool, typ)["varde"][:3]:
            ut["spel"].append({"typ": typ.capitalize(), "val": "-".join(map(str, v["kombo"])), "hast": "",
                               "chans": float(v["chans"]), "odds": float(v["odds"]),
                               "overvarde": float(v["overvarde"]), "insats": 10, "spel_id": f"{typ}_{l['lopp_id']}"})
        # Korspool: bara marknadens egna vinnarodds jämförda med den här potten (ingen egen spådom)
        for v in strategy.kombinationer(lopp, pm, pool, typ)["varde"][:2]:
            if v["overvarde"] >= config.KORSPOOL_OVERVARDE:
                ut["spel"].append({"typ": typ.capitalize() + "-pool", "val": "-".join(map(str, v["kombo"])),
                                   "hast": "", "chans": float(v["chans"]), "odds": float(v["odds"]),
                                   "overvarde": float(v["overvarde"]), "insats": 10,
                                   "spel_id": f"{typ}_{l['lopp_id']}"})
    for f in strategy.vinnare_plats(lopp, pm, bank):
        if f["typ"] == "Plats" and f["insats"] > 0 and f["overvarde"] >= config.KORSPOOL_OVERVARDE:
            ut["spel"].append({"typ": "Plats-pool", "val": str(f["nr"]), "hast": f["hast"], "chans": float(f["chans"]),
                               "odds": float(f["odds"]), "overvarde": float(f["overvarde"]),
                               "insats": f["insats"], "spel_id": f"vinnare_{l['lopp_id']}"})
    # Ta bort korspool-spel som redan finns som vanligt spel på samma val
    vanliga = {(s["typ"], s["val"]) for s in ut["spel"] if "-pool" not in s["typ"]}
    ut["spel"] = [s for s in ut["spel"] if "-pool" not in s["typ"] or (s["typ"][:-5], s["val"]) not in vanliga]
    return ut


def spara_lopp_spel(kassa, analys, bank, lagda=None):
    """Lägg loppets värdespel i papperskassan. Returnerar ny bankrulle (lagda spel läggs i listan lagda)."""
    for s in analys["spel"]:
        if 0 < s["insats"] <= bank and kassa.lagg(s["spel_id"], analys["lopp_id"], s["typ"], s["val"],
                                                  s["insats"], s["odds"], s["chans"], kommentar=s.get("hast", "")):
            bank -= s["insats"]
            if lagda is not None:
                lagda.append(s)
    return bank


def rorelse_fran_logg(logg_lopp, lopp_id):
    """Oddslogg {nr: [[min_kvar, odds], ...]} -> {(lopp_id, nr): log(tidigt odds / senaste odds)}.
    Positivt = hästen har spelats ner (pengar strömmar in)."""
    ut = {}
    for nr, punkter in (logg_lopp or {}).items():
        punkter = [p for p in punkter if p[1] and p[1] > 1]
        if len(punkter) < 2:
            continue
        tidiga = [p for p in punkter if p[0] >= 12] or [punkter[0]]
        tidig, sen = tidiga[-1], punkter[-1]
        if tidig[0] - sen[0] < 6:          # för kort tid mellan mätningarna för att säga något
            continue
        ut[(lopp_id, int(nr))] = math.log(tidig[1] / sen[1])
    return ut


def spara_system(kassa, analys, bank):
    """Spara det balanserade systemet om villkoren är uppfyllda."""
    sy = analys["system"]["Balanserad"]
    if config.SYSTEM_BARA_JACKPOTT and not analys.get("jackpott"):
        return bank
    if (analys["odds_oppna"] and sy["vardeindex"] >= analys["kravs"]
            and sy["kostnad"] <= bank * config.MAX_SYSTEM_ANDEL):
        if kassa.lagg(analys["id"], "", analys["typ"], sy["val"], sy["kostnad"], chans=sy["traffchans"],
                      kommentar=f"värdeindex {sy['vardeindex']:.2f}"):
            bank -= sy["kostnad"]
    return bank


# ---------------- AI-betyg av ATG:s spelkommentarer ----------------
def ai_betyg(klient, lopp_id, hastar):
    """Låter Claude läsa ATG:s kommentar för varje häst och ge -2..+2. Kräver ANTHROPIC_API_KEY.
    hastar: [(nr, namn)]. Returnerar {nr: poäng} eller {} om det inte gick."""
    nyckel = os.environ.get("ANTHROPIC_API_KEY")
    kom = klient.kommentarer(lopp_id) or {}
    if not nyckel or not kom:
        return {}
    rader = "\n".join(f"{nr} {namn}: {kom.get(str(nr), '(ingen kommentar)')}" for nr, namn in hastar)
    fraga = ("Du betygsätter travhästar inför ett lopp utifrån ATG:s korta spelkommentarer. "
             "Ge varje startnummer ett heltal från -2 (kommentaren talar tydligt emot hästen) till +2 "
             "(talar tydligt för). 0 om kommentaren är neutral eller saknas. Svara ENBART med JSON, "
             'till exempel {"1": 0, "2": 1}.\n\n' + rader)
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=40, headers={
            "x-api-key": nyckel, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": config.AI_MODELL, "max_tokens": 300, "messages": [{"role": "user", "content": fraga}]})
        r.raise_for_status()
        return tolka_ai_svar(r.json()["content"][0]["text"])
    except Exception as e:
        print(f"  (AI-betyg misslyckades: {e})")
        return {}


def tolka_ai_svar(text):
    start, slut = text.find("{"), text.rfind("}")
    if start < 0 or slut < 0:
        return {}
    try:
        d = json.loads(text[start:slut + 1])
    except ValueError:
        return {}
    ut = {}
    for k, v in d.items():
        try:
            ut[int(k)] = max(-2, min(2, int(v)))
        except (ValueError, TypeError):
            continue
    return ut


# ---------------- Notis till mobilen (ntfy.sh) ----------------
def notis(titel, text, prio="default"):
    """Skickar en notis till appen ntfy om NTFY_AMNE är satt (gratis, ingen inloggning)."""
    amne = os.environ.get("NTFY_AMNE")
    if not amne:
        return
    try:
        requests.post(f"https://ntfy.sh/{amne}", data=text.encode("utf-8"), timeout=10,
                      headers={"Title": titel.encode("utf-8"), "Priority": prio, "Tags": "horse"})
    except requests.RequestException as e:
        print(f"  (notis misslyckades: {e})")
