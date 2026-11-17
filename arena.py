"""
Arenan: flera bottar som lär sig och spelar på olika sätt, på exakt samma lopp.

Alla bottar pappersspelar Vinnare med samma insats (10 kr) i samma ögonblick (strax före start, på samma odds)
och rättas mot slutoddsen, precis som huvudboten. Då går det att jämföra dem rakt av.
Två av dem är måttstockar och inte riktiga bottar:
  * Favoriten – spelar alltid oddsfavoriten.
  * Slumpen   – spelar en slumpad häst. Visar vad ATG:s avdrag kostar om man inte kan något alls.
En bot är bara intressant om den slår båda över många spel.

Allt sparas i data/arena.csv. Modellvarianterna tränas av 'python bot.py arena-trana'.
"""
import contextlib
import io
import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

import config

INSATS = 10                     # kr per spel för alla bottar, så att avkastningen går att jämföra
MIN_SPEL_FOR_DOM = 100          # under så här många rättade spel är en bots siffror mest slump

KOLUMNER = ["skapad", "bot", "lopp_id", "spel_id", "nr", "hast", "insats", "odds", "chans",
            "status", "utbetalning"]

# Olika sätt att lära sig. 'huvud' är den vanliga modellen (models/modell.json).
MODELLER = {
    "huvud": "models/modell.json",
    "stram": "models/arena_stram.json",
    "flexibel": "models/arena_flexibel.json",
    "farsk": "models/arena_farsk.json",
}
MODELLNAMN = {"huvud": "Huvudmodellen", "stram": "Försiktiga modellen", "flexibel": "Flexibla modellen",
              "farsk": "Färska modellen", "rad": "Rådet (snitt av alla)", "fundamental": "Egen analys utan odds"}
CHANSKOLUMNER = ["lopp_id", "nr", "pm", "huvud", "stram", "flexibel", "farsk", "rad", "fundamental"]
VARIANTER = {   # hur varianterna tränas (l2 = hur hårt modellen hålls tillbaka, senaste = bara de N senaste loppen)
    "stram": {"l2": 8.0},
    "flexibel": {"l2": 0.1},
    "farsk": {"senaste": 1500},
}


# ---------------- spelregler ----------------
def _giltig(d):
    o = d["odds"]
    return np.isfinite(o) & (o > 1)


def _varde(modell, ev_min, p_min=None, ror_min=None, mot_marknad=None, max_per_lopp=None, rang_max=None):
    """Spela hästar där modellens chans * odds ger minst ev_min i förväntat värde.
    ror_min: kräver att hästen spelats ner i oddsen. mot_marknad: kräver chans >= x * marknadens.
    rang_max: bara hästar som modellen rankar bland de N bästa. max_per_lopp: bara de N med högst värde."""
    p_min = config.MIN_SANNOLIKHET if p_min is None else p_min

    def regel(d):
        p, o = d["p"][modell], d["odds"]
        o0 = np.where(np.isfinite(o), o, 0.0)
        ev = p * o0 - 1
        ok = _giltig(d) & (p >= p_min) & (ev >= ev_min)
        if ror_min is not None:
            ok &= np.nan_to_num(d["ror"], nan=-9.0) >= ror_min
        if mot_marknad is not None:
            ok &= p >= mot_marknad * d["pm"]
        if rang_max is not None:
            ok &= np.argsort(np.argsort(-p)) < rang_max
        idx = [int(i) for i in np.flatnonzero(ok)]
        if max_per_lopp is not None:
            idx = sorted(idx, key=lambda i: -ev[i])[:max_per_lopp]
        return idx
    return regel


def _favoriten(d):
    ok = np.flatnonzero(_giltig(d))
    return [] if len(ok) == 0 else [int(ok[np.argmin(d["odds"][ok])])]


def _slumpen(d):
    ok = [int(i) for i in np.flatnonzero(_giltig(d))]
    return [] if not ok else [random.Random(str(d["lopp_id"])).choice(ok)]


BOTTAR = [
    {"nyckel": "favoriten", "namn": "Favoriten", "ikon": "📏", "baslinje": True, "kraver": (), "regel": _favoriten,
     "forklaring": "Måttstock: spelar alltid oddsfavoriten, inget tänkande."},
    {"nyckel": "slumpen", "namn": "Slumpen", "ikon": "🎲", "baslinje": True, "kraver": (), "regel": _slumpen,
     "forklaring": "Måttstock: spelar en slumpad häst i varje lopp. Visar vad ATG:s avdrag kostar om man inte kan något."},
    {"nyckel": "huvud", "namn": "Huvudboten", "ikon": "🧠", "baslinje": False, "kraver": ("huvud",),
     "regel": _varde("huvud", 0.0),
     "forklaring": "Samma modell som den riktiga boten, men spelar redan när värdet är över 0 %. Den riktiga boten kräver "
                   f"+{config.MIN_OVERVARDE * 100:.0f} % och spelar därför nästan aldrig. Här behövs många spel för att kunna lära sig något."},
    {"nyckel": "stram", "namn": "Försiktige", "ikon": "🐢", "baslinje": False, "kraver": ("stram",),
     "regel": _varde("stram", 0.0),
     "forklaring": "Lär sig med mycket broms (L2 8). Litar mest på oddsen och ändrar sig lite."},
    {"nyckel": "flexibel", "namn": "Flexibla", "ikon": "🦎", "baslinje": False, "kraver": ("flexibel",),
     "regel": _varde("flexibel", 0.05),
     "forklaring": "Lär sig nästan utan broms (L2 0,1) och hittar fler mönster, men är brusigare och kräver därför +5 % värde."},
    {"nyckel": "farsk", "namn": "Färska", "ikon": "🌱", "baslinje": False, "kraver": ("farsk",),
     "regel": _varde("farsk", 0.0),
     "forklaring": "Lär sig bara av de senaste ca 1 500 loppen. Följer nutiden bättre men har mindre data att lära av."},
    {"nyckel": "rad", "namn": "Rådet", "ikon": "🗳️", "baslinje": False, "kraver": ("rad",),
     "regel": _varde("rad", 0.0),
     "forklaring": "Snittar alla modellernas chanser (ensemble) och spelar på snittet. Testar om flera huvuden tänker bättre än ett."},
    {"nyckel": "smarta", "namn": "Smarta pengar", "ikon": "💰", "baslinje": False, "kraver": ("huvud",),
     "regel": _varde("huvud", -1.0, p_min=0.0, ror_min=0.10, rang_max=3),
     "forklaring": "Spelar hästar som modellen rankar topp 3 och som spelats ner i oddsen sista halvtimmen. Testar om sena pengar vet något."},
    {"nyckel": "egen", "namn": "Egen åsikt", "ikon": "🧭", "baslinje": False, "kraver": ("fundamental",),
     "regel": _varde("fundamental", 0.30, mot_marknad=1.5, max_per_lopp=1),
     "forklaring": "Går bara på sin egen analys utan oddsen. Spelar en häst per lopp när den tror minst 50 % mer än marknaden."},
]
NAMN = {b["nyckel"]: b for b in BOTTAR}


# ---------------- modeller ----------------
def ladda_modeller(huvud=None):
    """Laddar de modeller som finns. huvud = redan inläst huvudmodell (sparar en inladdning)."""
    from model import Modell
    ut = {}
    for nyckel, fil in MODELLER.items():
        if nyckel == "huvud" and huvud is not None:
            ut[nyckel] = huvud
        elif Path(fil).exists():
            try:
                ut[nyckel] = Modell.ladda(fil)
            except (SystemExit, Exception) as e:
                print(f"  (arenan: hoppar över modellen '{nyckel}': {e})")
    return ut


def trana_varianter(df, visa=True):
    """Tränar modellvarianterna på samma data som huvudmodellen. Returnerar {variant: rapport}."""
    import forskare
    from model import Modell
    inst = forskare.las_installningar()
    df = df.sort_values(["datum", "lopp_id", "nr"], kind="stable")
    ut = {}
    for nyckel, v in VARIANTER.items():
        d = df
        if v.get("senaste"):
            ids = df.drop_duplicates("lopp_id").lopp_id.tail(v["senaste"])
            d = df[df.lopp_id.isin(set(ids))]
        m = Modell()
        m.l2 = v.get("l2", inst.get("l2", config.L2_STRAFF))
        m.avstangda = inst.get("avstangda", [])
        with contextlib.redirect_stdout(io.StringIO()):
            rapport = m.trana(d, visa=False)
        m.spara(MODELLER[nyckel])
        ut[nyckel] = {k: rapport[k] for k in ("antal_lopp", "testlopp", "loglik_marknad", "loglik_bot")}
        if visa:
            r = ut[nyckel]
            print(f"  {nyckel:9s} {r['antal_lopp']:5d} lopp  gissar {r['loglik_bot']:.4f}  oddsen {r['loglik_marknad']:.4f}  "
                  f"({'bättre' if r['loglik_bot'] > r['loglik_marknad'] else 'sämre'} än oddsen)")
    Path("models").mkdir(exist_ok=True)
    Path("models/arena_rapport.json").write_text(json.dumps(ut, indent=1), encoding="utf-8")
    return ut


# ---------------- beslut ----------------
def chanser(df, modeller):
    """Varje modells vinstchans per häst i ett lopp (df = ett lopp). Plus 'fundamental' och 'rad' (snitt)."""
    p = {k: np.asarray(m.p_slutlig(df), dtype=float) for k, m in modeller.items()}
    if "huvud" in modeller:
        p["fundamental"] = np.asarray(modeller["huvud"].p_fundamental(df), dtype=float)
    ens = [v for k, v in p.items() if k in MODELLER]
    if len(ens) >= 2:
        lp = np.mean([np.log(np.clip(v, 1e-6, None)) for v in ens], axis=0)
        e = np.exp(lp - lp.max())
        p["rad"] = e / e.sum()
    return p


def beslut(df, modeller):
    """df = ett lopp (en rad per häst, sorterad på nr) -> ({bot: [radindex, ...]}, underlag).
    Bottar som saknar sin modell hoppas över."""
    from model import marknads_p
    d = {"lopp_id": df["lopp_id"].iloc[0], "nr": df["nr"].values,
         "odds": pd.to_numeric(df["odds"], errors="coerce").values.astype(float),
         "pm": marknads_p(df).values,
         "ror": np.where(df["rorelse_saknas"].astype(bool), np.nan,
                         pd.to_numeric(df["rorelse"], errors="coerce")).astype(float),
         "p": chanser(df, modeller)}
    ut = {}
    for b in BOTTAR:
        if all(k in d["p"] for k in b["kraver"]):
            ut[b["nyckel"]] = b["regel"](d)
    return ut, d


# ---------------- spela och rätta ----------------
def las(data_dir="data"):
    f = Path(data_dir) / "arena.csv"
    if not f.exists():
        return pd.DataFrame(columns=KOLUMNER)
    return pd.read_csv(f)


def spela(klient, modeller, lopp, spel, rorelse, ai, data_dir="data", nu=None):
    """Alla bottar bestämmer sig för ett lopp strax före start. Returnerar antal sparade spel."""
    import motor
    df = motor.df_for_spel(spel, "vinnare", klient, rorelse, ai)
    if df.empty or pd.to_numeric(df["odds"], errors="coerce").isna().all():
        return 0
    if float(df["omsattning"].max() or 0) < config.MIN_OMSATTNING:
        return 0
    df = df.sort_values("nr").reset_index(drop=True)
    val, d = beslut(df, modeller)
    logga_chanser(df, d, data_dir)
    skapad = (nu or motor.nu()).isoformat(timespec="minutes")
    rader = []
    for bot, idx in val.items():
        kraver = NAMN[bot]["kraver"]
        chans = d["p"][kraver[0]] if kraver else d["pm"]     # måttstockarna har ingen egen chans: oddsens
        for i in idx:
            rader.append({"skapad": skapad, "bot": bot, "lopp_id": lopp["lopp_id"], "spel_id": f"vinnare_{lopp['lopp_id']}",
                          "nr": int(df["nr"].iloc[i]), "hast": df["hast"].iloc[i], "insats": INSATS,
                          "odds": float(d["odds"][i]), "chans": float(chans[i]),
                          "status": "öppen", "utbetalning": 0.0})
    if not rader:
        return 0
    gamla = las(data_dir)
    if not gamla.empty:
        har = set(zip(gamla.bot, gamla.lopp_id, gamla.nr.astype(int)))
        rader = [r for r in rader if (r["bot"], r["lopp_id"], r["nr"]) not in har]
    if rader:
        f = Path(data_dir) / "arena.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rader, columns=KOLUMNER).to_csv(f, mode="a", header=not f.exists(), index=False)
    return len(rader)


def logga_chanser(df, d, data_dir="data"):
    """Spara varje modells chans för alla hästar i loppet. Det är det bästa måttet på hur bra en modell lär sig:
    varje lopp ger en mätpunkt, medan spel med värde är sällsynta."""
    f = Path(data_dir) / "arena_chanser.csv"
    ut = pd.DataFrame({"lopp_id": d["lopp_id"], "nr": df["nr"].astype(int).values, "pm": d["pm"]})
    for k, v in d["p"].items():
        ut[k] = v
    ut = ut.reindex(columns=CHANSKOLUMNER)
    if f.exists():
        har = set(pd.read_csv(f, usecols=["lopp_id"]).lopp_id)
        if d["lopp_id"] in har:
            return
    f.parent.mkdir(parents=True, exist_ok=True)
    ut.round(5).to_csv(f, mode="a", header=not f.exists(), index=False)


def ratta(klient, data_dir="data"):
    """Rätta öppna arenaspel mot slutresultatet. Returnerar antal rättade."""
    import papper
    f = Path(data_dir) / "arena.csv"
    if not f.exists():
        return 0
    df = pd.read_csv(f)
    oppna = df[df.status == "öppen"]
    antal = 0
    for lopp_id in oppna.lopp_id.unique():
        spel = klient.spel(f"vinnare_{lopp_id}", farsk=True)
        if not spel or spel.get("status") != "results":
            continue
        for idx, r in oppna[oppna.lopp_id == lopp_id].iterrows():
            rad = pd.Series({"typ": "Vinnare", "lopp_id": lopp_id, "val": str(int(r.nr)), "insats": float(r.insats)})
            utb = papper.rattning(spel, rad)
            if utb is None:
                df.loc[idx, "status"] = "okänd"
                continue
            df.loc[idx, ["status", "utbetalning"]] = ["vunnen" if utb > 0 else "förlorad", round(utb, 2)]
            antal += 1
    if antal or (df.status == "okänd").any():
        df.to_csv(f, index=False)
    return antal


# ---------------- sammanställning ----------------
def sammanfatta(df):
    """En rad per bot: antal spel, avkastning och hur osäker den är."""
    ut = []
    for b in BOTTAR:
        g = df[df.bot == b["nyckel"]] if not df.empty else df
        r = g[g.status.isin(["vunnen", "förlorad"])] if not g.empty else g
        n = len(r)
        roi = se = None
        if n:
            per = (r.utbetalning - r.insats) / r.insats          # vinst per satsad krona i varje spel
            roi = float(per.mean())
            se = float(per.std(ddof=1) / math.sqrt(n)) if n > 1 else None
        ut.append({**{k: b[k] for k in ("nyckel", "namn", "ikon", "baslinje", "forklaring")},
                   "spel": int(len(g)), "rattade": int(n), "oppna": int((g.status == "öppen").sum()) if len(g) else 0,
                   "insats": float(r.insats.sum()) if n else 0.0, "tillbaka": float(r.utbetalning.sum()) if n else 0.0,
                   "netto": float(r.utbetalning.sum() - r.insats.sum()) if n else 0.0,
                   "traff": float((r.status == "vunnen").mean()) if n else None,
                   "roi": roi, "se": se})
    return ut


def gissning(data_dir="data"):
    """Hur bra gissar varje modell vinnaren jämfört med oddsen? Räknas över ALLA lopp, inte bara de man spelat på.
    Försprång > 0 = modellen gav vinnarna högre chans än oddsen gjorde. se = osäkerhet (ett standardfel)."""
    cf, rf = Path(data_dir) / "arena_chanser.csv", Path(data_dir) / "resultat.csv"
    if not (cf.exists() and rf.exists()):
        return []
    c = pd.read_csv(cf).drop_duplicates(["lopp_id", "nr"], keep="last")
    r = pd.read_csv(rf).drop_duplicates("lopp_id", keep="last")
    v = c.merge(r, on="lopp_id")
    v = v[v.nr == v.vinnare].drop_duplicates("lopp_id")
    ut = []
    for k in ("huvud", "stram", "flexibel", "farsk", "rad", "fundamental"):
        m = v.dropna(subset=[k])
        if m.empty:
            continue
        diff = np.log(m[k].clip(lower=1e-6)) - np.log(m.pm.clip(lower=1e-6))
        n = len(diff)
        ut.append({"nyckel": k, "namn": MODELLNAMN[k], "lopp": int(n), "fors": float(np.expm1(diff.mean())),
                   "se": float(diff.std(ddof=1) / math.sqrt(n)) if n > 1 else None})
    return sorted(ut, key=lambda x: -x["fors"])


def dom(rad, tavla):
    """Kort bedömning av en bot mot måttstockarna. Returnerar (text, klass)."""
    if rad["baslinje"]:
        return "måttstock", ""
    if rad["rattade"] < MIN_SPEL_FOR_DOM:
        return f"för tidigt ({rad['rattade']}/{MIN_SPEL_FOR_DOM})", ""
    bas = [t["roi"] for t in tavla if t["baslinje"] and t["roi"] is not None and t["rattade"] >= MIN_SPEL_FOR_DOM]
    if bas and rad["roi"] <= max(bas):
        return "slår inte måttstockarna", "förlorad"
    if rad["se"] is not None and rad["roi"] - 2 * rad["se"] > 0:
        return "tydligt plus", "vunnen"
    return "bättre än måttstockarna, men ännu inte bevisat", "öppen"
