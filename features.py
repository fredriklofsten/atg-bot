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
    # form senaste starterna (från hästens resultatlista)
    "log_dagar_vila", "lang_vila", "vila_saknas", "galopp_senaste", "galopp_andel5", "disk_senaste",
    "form5", "seger_senaste", "km5_rel", "log_odds_senaste", "forsta_barfota", "kuskbyte", "kuskbyte_topp",
    # bana
    "tung_bana", "vinterbana", "hemmabana",
    # marknadsrörelse och AI (lärs in när data finns, se model.py)
    "rorelse", "rorelse_saknas", "ai_poang", "ai_saknas",
]
# Egenskaper som saknar historik från start. Tills modellen sett nog med lopp används en försiktig förhandsvikt.
FORHANDSVIKT = {"rorelse": 0.3, "ai_poang": 0.08}


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


PLACPOANG = {"1": 1.0, "2": 0.6, "3": 0.4, "4": 0.2, "5": 0.1}


def form_fran_resultat(resultat, datum, nu_barfota, kusk_id, kusk_pct):
    """Form-egenskaper ur hästens tidigare lopp – bara lopp FÖRE datum räknas."""
    tom = {"log_dagar_vila": float("nan"), "lang_vila": 0, "vila_saknas": 1, "galopp_senaste": 0,
           "galopp_andel5": 0.0, "disk_senaste": 0, "form5": float("nan"), "seger_senaste": 0,
           "km5": float("nan"), "log_odds_senaste": float("nan"), "forsta_barfota": 0,
           "kuskbyte": 0, "kuskbyte_topp": 0, "form_txt": "", "dagar_vila": None}
    recs = [r for r in (resultat or {}).get("records", []) or []
            if r.get("date", "9999") < datum and g(r, "race", "type") != "qualifier"]
    if not recs:
        return tom
    recs.sort(key=lambda r: r["date"], reverse=True)
    sen = recs[0]
    fem = recs[:5]
    from datetime import date as _d
    dagar = (_d.fromisoformat(datum) - _d.fromisoformat(sen["date"])).days
    tider = [km_tid(r.get("kmTime")) for r in fem]
    tider = [t for t in tider if t and 60 < t < 100]
    odds = sen.get("odds")
    skor_fore = g(sen, "start", "horse", "shoes", default={}) or {}
    hade_skor = skor_fore.get("front") is True and skor_fore.get("back") is True
    byte = 1 if g(sen, "start", "driver", "id") and kusk_id and g(sen, "start", "driver", "id") != kusk_id else 0
    return {
        "log_dagar_vila": math.log1p(dagar), "lang_vila": 1 if dagar > 60 else 0, "vila_saknas": 0,
        "galopp_senaste": 1 if sen.get("galloped") else 0,
        "galopp_andel5": sum(1 for r in fem if r.get("galloped")) / len(fem),
        "disk_senaste": 1 if sen.get("disqualified") else 0,
        "form5": (sum(PLACPOANG.get(str(r.get("place")), 0) for r in fem) + 0.25 * 2) / (len(fem) + 2),
        "seger_senaste": 1 if str(sen.get("place")) == "1" else 0,
        "km5": min(tider) if tider else float("nan"),
        "log_odds_senaste": math.log(odds / 100) if odds and odds > 100 else float("nan"),
        "forsta_barfota": 1 if (nu_barfota and hade_skor) else 0,
        "kuskbyte": byte, "kuskbyte_topp": 1 if byte and kusk_pct >= 0.15 else 0,
        # bara för visning (som i programmet hos ett ombud)
        "form_txt": " ".join(("d" if r.get("disqualified") else
                              (str(r.get("place")) if str(r.get("place")) in "123456789" and r.get("place") else "0")
                              + ("g" if r.get("galloped") else "")) for r in fem),
        "dagar_vila": dagar,
    }


def stat_ar(stats, ar):
    years = g(stats, "years", default={}) or {}
    return years.get(str(ar)) or {}


def rader_fran_spel(spel, speltyp=None, klient=None, rorelse=None, ai=None):
    """En rad per (lopp, häst) ur ett spel-JSON.
    klient: hämtar hästarnas formrader. rorelse/ai: {(lopp_id, nr): värde} från vaktläget."""
    rorelse = rorelse or {}
    ai = ai or {}
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
            barfota_nu = (g(hast, "shoes", "front", "hasShoe") is False) or (g(hast, "shoes", "back", "hasShoe") is False)
            kusk_pct = krympt_pct(g(kusk, "placement", "1", default=0), kusk.get("starts", 0) or 0, 0.08, 30)
            res = klient.hast_resultat(hast["id"]) if (klient is not None and hast.get("id")) else None
            form = form_fran_resultat(res, datum, barfota_nu, g(s, "driver", "id"), kusk_pct)
            skick = g(lopp, "track", "condition")
            rr = rorelse.get((lopp["id"], s.get("number")))
            aa = ai.get((lopp["id"], s.get("number")))
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
                "kusk_seger_pct": kusk_pct,
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
                **form,
                "km5_rel": float("nan"),
                "tung_bana": 1 if skick in ("dead", "heavy") else 0,
                "vinterbana": 1 if skick == "winter" else 0,
                "hemmabana": 1 if g(hast, "homeTrack", "id") and g(hast, "homeTrack", "id") == g(lopp, "track", "id") else 0,
                "rorelse": rr if rr is not None else 0.0, "rorelse_saknas": 0 if rr is not None else 1,
                "ai_poang": aa if aa is not None else 0.0, "ai_saknas": 0 if aa is not None else 1,
                "tranare": f"{g(hast, 'trainer', 'firstName', default='')} {g(hast, 'trainer', 'lastName', default='')}".strip(),
                "kon": {"mare": "sto", "stallion": "hingst", "gelding": "valack"}.get(hast.get("sex"), ""),
                "spar": spar, "avstand": avst, "startmetod": "auto" if auto else "volt",
                "rekord_txt": (f"{g(hast,'record','time','minutes', default=1)}.{g(hast,'record','time','seconds', default=0):02d},"
                               f"{g(hast,'record','time','tenths', default=0)}{g(hast,'record','code', default='')}") if rek else "",
                "intjanat": intj, "liv_starter": liv_st, "liv_1": v1, "liv_2": v2, "liv_3": v3,
                "skor_txt": ("barfota runt om" if (g(hast, "shoes", "front", "hasShoe") is False and g(hast, "shoes", "back", "hasShoe") is False)
                             else "barfota fram" if g(hast, "shoes", "front", "hasShoe") is False
                             else "barfota bak" if g(hast, "shoes", "back", "hasShoe") is False else ""),
                "loppnamn": lopp.get("name", ""),
                "hast_id": hast.get("id"), "kusk_id": g(s, "driver", "id"), "bana_id": g(lopp, "track", "id"),
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
    if "km5" in df:
        snitt5 = df.groupby("lopp_id")["km5"].transform("mean")
        df["km5_rel"] = (df["km5"] - snitt5).fillna(0.0)
    return df


def forbered_X(df, medel=None, std=None):
    """Fyll saknade värden och standardisera. Returnerar X, medel, std."""
    X = df[FEATURES].apply(pd.to_numeric, errors="coerce").astype(float)
    if medel is None:
        medel = X.mean().fillna(0.0)
        std = X.std().replace(0, 1).fillna(1)
    X = X.fillna(medel).fillna(0.0)
    X = (X - medel) / std
    return X.values, medel, std


def las_loggar(data_dir="data"):
    """Oddsrörelser och AI-betyg som vaktläget sparat: {(lopp_id, nr): värde}."""
    ut = []
    for namn, kol in (("rorelse.csv", "rorelse"), ("ai_betyg.csv", "ai_poang")):
        f = Path(data_dir) / namn
        d = {}
        if f.exists():
            t = pd.read_csv(f).drop_duplicates(["lopp_id", "nr"], keep="last")
            d = {(r.lopp_id, int(r.nr)): float(getattr(r, kol)) for r in t.itertuples()}
        ut.append(d)
    return ut


def bygg_dataset(dagar, data_dir="data", offline=False, visa=True):
    """Hämtar alla färdiga lopp för angivna dagar och sparar data/dataset.csv."""
    klient = ATGKlient(data_dir, offline=offline)
    alla = []
    for i, dag in enumerate(dagar, 1):
        kal = klient.kalender(dag)
        lopp = [l for l in lopp_i_kalender(kal) if l["status"] == "results"]
        for l in lopp:
            spel = klient.spel(f"vinnare_{l['lopp_id']}")
            alla.extend(rader_fran_spel(spel, "vinnare", klient, *las_loggar(data_dir)))
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
