"""
Gör om ATG:s rådata till en tabell: en rad per häst och lopp.
Det är här botens "travkunskap" bor – vilka egenskaper (features) den tittar på.
Läs KUNSKAP.md för varför varje sak spelar roll.
"""
import math
from pathlib import Path

import pandas as pd

import config
from atg_api import ATGKlient, lopp_i_kalender

# De egenskaper modellen lär sig av (marknadens odds hålls utanför – de används i steg 2)
FEATURES = [
    "auto", "spar_inner", "spar_ytter", "andra_led", "volt_spar_dalig", "tillagg_20m",
    "alder", "ar_3", "hingst", "sto",
    "log_intjanat", "log_starter", "seger_pct", "topp3_pct", "log_per_start",
    "ar_seger_pct", "ar_starter_log", "ar_form_saknas",
    "rekord_km", "rekord_saknas", "rekord_rel",
    "kusk_seger_pct", "kusk_starter_log", "tranare_seger_pct",
    "barfota_fram", "barfota_bak", "skobyte", "amerikansk_vagn",
    "log_snittodds5", "snittodds_saknas", "startpoang",
    "lang_distans", "kort_distans",
]


def g(d, *nycklar, default=None):
    """Säker uppslagning i nästlade dictionaries: g(start, 'horse', 'age')."""
    for k in nycklar:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d if d is not None else default


def km_tid(t):
    """{'minutes':1,'seconds':13,'tenths':2} -> 73.2 sekunder per km."""
    if not isinstance(t, dict) or "seconds" not in t:
        return None
    return t.get("minutes", 0) * 60 + t.get("seconds", 0) + t.get("tenths", 0) / 10


def krympt_pct(vinster, starter, prior, styrka):
    """Vinstprocent som dras mot ett snitt när det finns få starter (1 av 1 är inte 100 %)."""
    return (vinster + prior * styrka) / (starter + styrka)


def stat_ar(stats, ar):
    years = g(stats, "years", default={}) or {}
    return years.get(str(ar)) or {}


def rader_fran_spel(spel, speltyp=None):
    """En rad per (lopp, häst) ur ett spel-JSON."""
    rader = []
    if not spel:
        return rader
    speltyp = speltyp or spel.get("type") or spel.get("id", "").split("_")[0]
    for lopp in spel.get("races", []):
        datum = lopp.get("date") or lopp["id"][:10]
        ar = int(datum[:4])
        auto = 1 if lopp.get("startMethod") == "auto" else 0
        distans = lopp.get("distance") or 2140
        starter = [s for s in lopp.get("starts", []) if not s.get("scratched")]
        n = len(starter)
        for s in starter:
            hast = s.get("horse", {})
            liv = g(hast, "statistics", "life", default={})
            liv_st = liv.get("starts", 0) or 0
            liv_pl = liv.get("placement", {}) or {}
            v1, v2, v3 = (liv_pl.get(k, 0) or 0 for k in ("1", "2", "3"))
            intj = (liv.get("earnings", 0) or 0) / 100
            arst = stat_ar(hast.get("statistics"), ar)
            ar_st = arst.get("starts", 0) or 0
            ar_v = g(arst, "placement", "1", default=0)
            kusk = stat_ar(g(s, "driver", "statistics"), ar) or stat_ar(g(s, "driver", "statistics"), ar - 1)
            tran = stat_ar(g(hast, "trainer", "statistics"), ar) or stat_ar(g(hast, "trainer", "statistics"), ar - 1)
            rek = km_tid(g(hast, "record", "time"))
            spar = s.get("postPosition") or s.get("number") or 0
            avst = s.get("distance") or distans
            snitt5 = g(hast, "statistics", "lastFiveStarts", "averageOdds")
            pools = s.get("pools", {}) or {}
            vodds = g(pools, "vinnare", "odds") or g(s, "result", "finalOdds")
            if vodds and vodds > 50:          # ATG skickar odds*100 (351 = 3.51)
                vodds = vodds / 100
            podds = g(pools, "plats", "minOdds")
            strk = g(pools, speltyp, "betDistribution") if speltyp else None
            plac = g(s, "result", "place")
            rader.append({
                # --- id-info ---
                "lopp_id": lopp["id"], "datum": datum, "starttid": lopp.get("startTime"),
                "bana": g(lopp, "track", "name"), "lopp_nr": lopp.get("number"),
                "nr": s.get("number"), "hast": hast.get("name"),
                "kusk": f"{g(s, 'driver', 'firstName', default='')} {g(s, 'driver', 'lastName', default='')}".strip(),
                "antal": n, "distans": distans, "status": lopp.get("status"),
                # --- egenskaper ---
                "auto": auto,
                "spar_inner": 1 if auto and spar <= 3 else 0,
                "spar_ytter": 1 if auto and 6 <= spar <= 8 else 0,
                "andra_led": 1 if auto and spar >= 9 else 0,
                "volt_spar_dalig": 1 if (not auto) and spar in (8, 9, 10, 11, 12) and avst == distans else 0,
                "tillagg_20m": (avst - distans) / 20,
                "alder": hast.get("age") or 5,
                "ar_3": 1 if hast.get("age") == 3 else 0,
                "hingst": 1 if hast.get("sex") == "stallion" else 0,
                "sto": 1 if hast.get("sex") == "mare" else 0,
                "log_intjanat": math.log1p(intj),
                "log_starter": math.log1p(liv_st),
                "seger_pct": krympt_pct(v1, liv_st, 0.10, 8),
                "topp3_pct": krympt_pct(v1 + v2 + v3, liv_st, 0.30, 8),
                "log_per_start": math.log1p(intj / liv_st) if liv_st else 0.0,
                "ar_seger_pct": krympt_pct(ar_v, ar_st, 0.10, 5),
                "ar_starter_log": math.log1p(ar_st),
                "ar_form_saknas": 1 if ar_st == 0 else 0,
                "rekord_km": rek if rek else float("nan"),
                "rekord_saknas": 0 if rek else 1,
                "rekord_rel": float("nan"),     # fylls i nedan (jämfört med loppets snitt)
                "kusk_seger_pct": krympt_pct(g(kusk, "placement", "1", default=0), kusk.get("starts", 0) or 0, 0.08, 30),
                "kusk_starter_log": math.log1p(kusk.get("starts", 0) or 0),
                "tranare_seger_pct": krympt_pct(g(tran, "placement", "1", default=0), tran.get("starts", 0) or 0, 0.08, 30),
                "barfota_fram": 0 if g(hast, "shoes", "front", "hasShoe", default=True) else 1,
                "barfota_bak": 0 if g(hast, "shoes", "back", "hasShoe", default=True) else 1,
                "skobyte": 1 if (g(hast, "shoes", "front", "changed") or g(hast, "shoes", "back", "changed")) else 0,
                "amerikansk_vagn": 1 if g(hast, "sulky", "type", "code") == "AM" else 0,
                "log_snittodds5": math.log(snitt5 / 100) if snitt5 else float("nan"),
                "snittodds_saknas": 0 if snitt5 else 1,
                "startpoang": (liv.get("startPoints") or 0) / 1000,
                "lang_distans": 1 if distans >= 2600 else 0,
                "kort_distans": 1 if distans <= 1700 else 0,
                # --- marknad (vad spelarna tror) ---
                "odds": vodds, "plats_odds": podds / 100 if podds else None,
                "streck": strk / 100 if strk is not None else None,   # procent
                "speltyp": speltyp,
                "omsattning": (g(lopp, "pools", "vinnare", "turnover", default=0) or 0) / 100,  # kr i vinnarpoolen
                # --- facit ---
                "placering": plac,
                "vann": (1 if plac == 1 else 0) if plac is not None else None,
                "slutodds": g(s, "result", "finalOdds"),
            })
    df = pd.DataFrame(rader)
    if not df.empty:
        df = fyll_relativa(df)
    return df.to_dict("records")


def fyll_relativa(df):
    """Jämför hästen med de andra i samma lopp (rekordtid relativt fältet)."""
    snitt = df.groupby("lopp_id")["rekord_km"].transform("mean")
    df["rekord_rel"] = (df["rekord_km"] - snitt).fillna(0.0)
    return df


def forbered_X(df, medel=None, std=None):
    """Fyll saknade värden och standardisera. Returnerar X, medel, std."""
    X = df[FEATURES].apply(pd.to_numeric, errors="coerce").astype(float)
    if medel is None:
        medel = X.mean()
        std = X.std().replace(0, 1).fillna(1)
    X = X.fillna(medel)
    X = (X - medel) / std
    return X.values, medel, std


def bygg_dataset(dagar, data_dir="data", offline=False, visa=True):
    """Hämtar alla färdiga lopp för angivna dagar och sparar data/dataset.csv."""
    klient = ATGKlient(data_dir, offline=offline)
    alla = []
    for i, dag in enumerate(dagar, 1):
        kal = klient.kalender(dag)
        lopp = [l for l in lopp_i_kalender(kal) if l["status"] == "results"]
        for l in lopp:
            spel = klient.spel(f"vinnare_{l['lopp_id']}")
            alla.extend(rader_fran_spel(spel, "vinnare"))
        if visa:
            print(f"  {dag}: {len(lopp)} lopp  ({i}/{len(dagar)})")
    df = pd.DataFrame(alla)
    if df.empty:
        return df
    df = df.drop_duplicates(["lopp_id", "nr"])
    ut = Path(data_dir) / "dataset.csv"
    if ut.exists():   # slå ihop med tidigare insamlat
        gammal = pd.read_csv(ut)
        df = pd.concat([gammal, df]).drop_duplicates(["lopp_id", "nr"], keep="last")
    df = df.sort_values(["datum", "lopp_id", "nr"])
    df.to_csv(ut, index=False)
    return df
