"""
AI-forskaren: testar en ny idé i veckan, ärligt.

1. PLANERA – skriver ner hypotesen och exakt vilket resultat som krävs INNAN testet körs.
   Planen sparas och laddas upp till GitHub först, så ingen kan ändra reglerna i efterhand.
2. KÖR     – testar idén på de senaste månaderna (tränar på det som var före, testar på månaden efter).
3. BESLUT  – idén förs bara in i boten om den vann enligt de förregistrerade reglerna.
Allt loggas i data/labbdagbok.json och visas i appen.
"""
import contextlib
import io
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from features import FEATURES
from model import Modell, rena_lopp

PLANFIL = Path("data/forskning_plan.json")
DAGBOK = Path("data/labbdagbok.json")
INSTALLNINGAR = Path("models/installningar.json")

GRUPPER = {
    "form": ["log_dagar_vila", "lang_vila", "vila_saknas", "galopp_senaste", "galopp_andel5", "disk_senaste",
             "form5", "seger_senaste", "km5_rel", "log_odds_senaste"],
    "utrustning": ["barfota_fram", "barfota_bak", "skobyte", "amerikansk_vagn", "forsta_barfota"],
    "kusk_tranare": ["kusk_seger_pct", "kusk_starter_log", "tranare_seger_pct", "kuskbyte", "kuskbyte_topp"],
    "bana": ["tung_bana", "vinterbana", "hemmabana"],
    "spar": ["spar_inner", "spar_ytter", "andra_led", "volt_spar_dalig"],
    "pengar": ["log_intjanat", "log_per_start", "startpoang"],
}

# Idéerna testas i tur och ordning, en per vecka. Varje idé är en ändring mot nuvarande inställningar.
HYPOTESER = [
    {"id": "l2_svagare", "text": "Mindre återhållsam modell (L2 0,3 i stället för 1,0) gissar bättre", "l2": 0.3},
    {"id": "l2_starkare", "text": "Mer återhållsam modell (L2 3,0) gissar bättre", "l2": 3.0},
    {"id": "utan_form", "text": "Formdatan från senaste starterna tillför inget (ta bort den)", "bort": "form"},
    {"id": "utan_utrustning", "text": "Skor och vagn tillför inget (ta bort dem)", "bort": "utrustning"},
    {"id": "utan_kusk", "text": "Kusk- och tränarstatistik tillför inget (ta bort den)", "bort": "kusk_tranare"},
    {"id": "utan_bana", "text": "Banans skick och hemmabana tillför inget (ta bort dem)", "bort": "bana"},
    {"id": "utan_spar", "text": "Spåren tillför inget utöver oddsen (ta bort dem)", "bort": "spar"},
    {"id": "utan_pengar", "text": "Intjänade pengar tillför inget utöver oddsen (ta bort dem)", "bort": "pengar"},
]

KRAV = {"min_forbattring": 0.002, "min_manader_battre": 4, "antal_manader": 5}


def las_installningar():
    if INSTALLNINGAR.exists():
        return json.loads(INSTALLNINGAR.read_text(encoding="utf-8"))
    return {"l2": 1.0, "avstangda": []}


def _dagbok():
    return json.loads(DAGBOK.read_text(encoding="utf-8")) if DAGBOK.exists() else []


def planera():
    """Välj veckans hypotes och skriv ner reglerna innan något testas."""
    gjorda = {d["id"] for d in _dagbok()}
    kvar = [h for h in HYPOTESER if h["id"] not in gjorda] or HYPOTESER   # alla gjorda -> börja om
    h = kvar[0]
    plan = {"datum": date.today().isoformat(), **h, "matt": "snitt-loglik för vinnaren per lopp (botens slutliga chans)",
            "regel": (f"Införs bara om snittet förbättras med minst {KRAV['min_forbattring']} OCH idén är bättre "
                      f"i minst {KRAV['min_manader_battre']} av de {KRAV['antal_manader']} senaste månaderna."),
            "utgangslage": las_installningar()}
    PLANFIL.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Veckans hypotes:", h["text"])
    return plan


def _variant(bas, h):
    v = {"l2": bas.get("l2", 1.0), "avstangda": list(bas.get("avstangda", []))}
    if "l2" in h:
        v["l2"] = h["l2"]
    if "bort" in h:
        v["avstangda"] = sorted(set(v["avstangda"]) | set(GRUPPER[h["bort"]]))
    return v


def _trana(df, inst):
    m = Modell()
    m.l2 = inst["l2"]
    m.avstangda = inst["avstangda"]
    with contextlib.redirect_stdout(io.StringIO()):
        m.trana(df, visa=False)
    return m


def utvardera(df, inst, manader):
    """Loglik per testmånad för en inställning."""
    ut = []
    for man in manader:
        tr, te = df[df.man < man], df[df.man == man].sort_values(["datum", "lopp_id", "nr"])
        m = _trana(tr, inst)
        te = te.copy()
        y = te["vann"].values == 1
        ut.append(float(np.mean(np.log(m.p_slutlig(te)[y]))))
    return ut


def kor(df=None):
    """Kör den planerade hypotesen och fatta beslut enligt planen."""
    if not PLANFIL.exists():
        print("Ingen plan – kör planera först.")
        return None
    plan = json.loads(PLANFIL.read_text(encoding="utf-8"))
    if df is None:
        df = pd.read_csv("data/dataset.csv")
    df = rena_lopp(df)
    for c in FEATURES:
        if c not in df:
            df[c] = np.nan
    df["man"] = df.datum.str[:7]
    manader = sorted(df.man.unique())[-KRAV["antal_manader"]:]
    bas = plan["utgangslage"]
    variant = _variant(bas, plan)
    a = utvardera(df, bas, manader)
    b = utvardera(df, variant, manader)
    diff = [y - x for x, y in zip(a, b)]
    battre = sum(1 for d in diff if d > 0)
    infors = np.mean(diff) >= KRAV["min_forbattring"] and battre >= KRAV["min_manader_battre"]
    post = {"id": plan["id"], "datum": date.today().isoformat(), "planerad": plan["datum"], "text": plan["text"],
            "regel": plan["regel"], "manader": manader, "fore": a, "efter": b,
            "snitt_forbattring": float(np.mean(diff)), "battre_manader": battre, "infors": bool(infors)}
    if infors:
        INSTALLNINGAR.parent.mkdir(exist_ok=True)
        INSTALLNINGAR.write_text(json.dumps(variant, ensure_ascii=False, indent=1), encoding="utf-8")
    bok = _dagbok() + [post]
    DAGBOK.write_text(json.dumps(bok, ensure_ascii=False, indent=1), encoding="utf-8")
    PLANFIL.unlink()
    print(f"{plan['text']}: {'INFÖRS' if infors else 'förkastas'} "
          f"(snitt {np.mean(diff):+.4f}, bättre {battre}/{len(diff)} månader)")
    return post
