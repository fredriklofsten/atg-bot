"""
Analysmotorn: tar ett V-spel eller ett lopp och räknar fram botens förslag.
Används både av 'tips' (du kör själv) och 'automat' (GitHub kör var 10:e minut).
"""
import os
from datetime import datetime

import numpy as np
import pandas as pd

import config
import strategy
from features import rader_fran_spel

SYSTEMNAMN = (("Försiktig", 0.3), ("Balanserad", 1.0), ("Skrällvänlig", 2.0))


def nu():
    """Aktuell svensk tid. ATG_NU='2026-11-16T18:10' låter dig testa som om klockan vore något annat."""
    if os.environ.get("ATG_NU"):
        return datetime.fromisoformat(os.environ["ATG_NU"])
    return datetime.now()


def minuter_kvar(starttid):
    """Minuter tills start (negativt = har startat). starttid = '2026-11-16T18:20:00' (svensk tid)."""
    try:
        return (datetime.fromisoformat(str(starttid)[:19]) - nu()).total_seconds() / 60
    except ValueError:
        return None


def df_for_spel(spel, typ):
    df = pd.DataFrame(rader_fran_spel(spel, typ))
    if df.empty:
        return df
    return df.sort_values(["lopp_nr", "nr"]).reset_index(drop=True)


def analysera_system(klient, modell, g, budget):
    """V-spel -> dict med avdelningar och tre system. None om data saknas."""
    spel = klient.spel(g["id"], farsk=True)
    df = df_for_spel(spel, g["typ"])
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
    return {"id": g["id"], "typ": g["typ"], "bana": g["bana"], "start": g.get("startTime"),
            "avdrag": avdrag, "kravs": 1 / (1 - avdrag), "odds_oppna": odds_oppna,
            "avdelningar": visning, "system": system}


def analysera_lopp(klient, modell, l, bank):
    """Ett lopp -> dict med favoriter och värdespel (Vinnare, Plats, Trio, Tvilling)."""
    spel = klient.spel(f"vinnare_{l['lopp_id']}", farsk=True)
    df = df_for_spel(spel, "vinnare")
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
                        "odds": float(lopp[i]["odds"]) if lopp[i]["odds"] else None} for i in ordning[:4]]
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
    return ut


def spara_lopp_spel(kassa, analys, bank):
    """Lägg loppets värdespel i papperskassan. Returnerar ny bankrulle."""
    for s in analys["spel"]:
        if 0 < s["insats"] <= bank and kassa.lagg(s["spel_id"], analys["lopp_id"], s["typ"], s["val"],
                                                  s["insats"], s["odds"], s["chans"]):
            bank -= s["insats"]
    return bank


def spara_system(kassa, analys, bank):
    """Spara det balanserade systemet om villkoren är uppfyllda."""
    sy = analys["system"]["Balanserad"]
    if (analys["odds_oppna"] and sy["vardeindex"] >= analys["kravs"]
            and sy["kostnad"] <= bank * config.MAX_SYSTEM_ANDEL):
        if kassa.lagg(analys["id"], "", analys["typ"], sy["val"], sy["kostnad"], chans=sy["traffchans"],
                      kommentar=f"värdeindex {sy['vardeindex']:.2f}"):
            bank -= sy["kostnad"]
    return bank
