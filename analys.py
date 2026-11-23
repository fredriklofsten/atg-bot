"""
Förlustanalys och lärdomar: boten lär sig av sina avgjorda spel, särskilt de förlorade.

1. ANALYS  – varje avgjort spel (huvudboten och arenan) får en rad i data/spelanalys.csv:
             var hästen kom, vem som vann, slutoddset och en orsak till förlusten.
2. LÄRDOMAR – spelen grupperas (speltyp, oddsnivå, hur mycket boten trodde mer än marknaden, rörelse ...).
             I varje grupp jämförs antalet träffar med hur många boten själv räknade med.
             Bara skillnader som är för stora för att vara slump (|z| >= 2,5) räknas som lärdomar.
             Allt annat är brus och lärs INTE in. Det skyddar boten från att lära sig fel saker.
3. FÖRSIKTIGHET – träffar boten mer sällan än den tror i en speltyp sänks dess chans där
             automatiskt. Det går bara åt det försiktiga hållet och krymps mot 1 när datan är liten.

Resultatet sparas i data/lardomar.json och visas i appen under Utveckling.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import config

ANALYSFIL = "spelanalys.csv"
LARDOMSFIL = "lardomar.json"
MAX_NYA_LOPP = 40          # så många nya lopp hämtas per körning (vaktandet får aldrig bli efter)
Z_LARDOM = 2.5             # så här säker måste en skillnad vara för att räknas som lärdom (många grupper testas)
MIN_SPEL_LARDOM = 30       # minst så många spel i gruppen
MIN_SPEL_FORSIKTIG = 20    # försiktigheten börjar gälla efter så många spel i speltypen
PRIOR_TRAFFAR = 3.0        # "låtsasträffar" som gör att några få förluster inte ändrar mycket
MIN_FAKTOR = 0.5           # botens chans sänks aldrig mer än till hälften

KOLUMNER = ["nyckel", "kalla", "skapad", "spel_id", "lopp_id", "typ", "val", "insats", "odds", "chans",
            "status", "utbetalning", "marknadschans", "kvot", "placering", "antal", "vinnare", "vinnarodds",
            "slutodds", "clv", "ratt_delar", "delar", "rorelse", "startmetod", "orsak"]

ORSAKER = {
    "vann": "Vann",
    "nara": "Nära (precis utanför)",
    "mitten": "Mitt i fältet",
    "langt_efter": "Långt efter",
    "galopp_disk": "Galopp eller diskad",
    "skrall": "En skräll vann",
    "oddsen_steg": "Marknaden trodde mindre efter spelet",
    "struken": "Struken",
    "en_avd_fel": "En avdelning fel",
    "flera_avd_fel": "Flera avdelningar fel",
}


# ---------------- hjälpare ----------------
def _avdrag(typ):
    t = str(typ).split("-")[0].lower()
    return config.AVDRAG.get(t, config.AVDRAG.get(str(typ).split("-")[0], 0.2))


def marknadschans(typ, odds):
    """Marknadens chans ur oddset när spelet lades (efter ATG:s avdrag)."""
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(o) or o <= 1:
        return None
    return (1 - _avdrag(typ)) / o


def band(mc):
    """Oddsnivå uttryckt som marknadens chans."""
    if mc is None or not np.isfinite(mc):
        return None
    for grans, namn in ((0.30, "favorit (>30 %)"), (0.15, "15–30 %"), (0.07, "7–15 %"), (0.03, "3–7 %")):
        if mc >= grans:
            return namn
    return "långskott (<3 %)"


def kvotband(k):
    if k is None or not np.isfinite(k):
        return None
    if k < 1.25:
        return "tror lite mer än marknaden (<1,25×)"
    if k < 1.75:
        return "tror klart mer (1,25–1,75×)"
    if k < 2.5:
        return "tror mycket mer (1,75–2,5×)"
    return "tror extremt mycket mer (>2,5×)"


def _starter(spel, lopp_id=None):
    """{nr: start} för loppet (eller första loppet)."""
    for lopp in (spel or {}).get("races", []):
        if lopp_id is None or lopp.get("id") == lopp_id:
            return {int(s["number"]): s for s in lopp.get("starts", [])}, lopp
    return {}, None


def _plac(start):
    """(placering, galopperade, diskad). Placering = målgångsordning, 0 om okänd eller diskad
    (ATG ger diskade hästar målgång 40+)."""
    res = (start or {}).get("result") or {}
    fo = int(res.get("finishOrder") or res.get("place") or 0)
    disk = bool(res.get("disqualified")) or fo >= 30
    return (0 if disk else fo), bool(res.get("galloped")), disk


# ---------------- 1. analys av enskilda spel ----------------
def _analysera_lopp_spel(r, spel, ror):
    typ = str(r["typ"]).split("-")[0]
    starts, lopp = _starter(spel, r["lopp_id"])
    if not starts:
        return None
    antal = sum(1 for s in starts.values() if not s.get("scratched"))
    ordning = {}
    for nr, s in starts.items():
        fo, _, _ = _plac(s)
        if fo:
            ordning[fo] = nr
    vinnare = ordning.get(1)
    vinnarodds = (starts.get(vinnare, {}).get("result") or {}).get("finalOdds") if vinnare else None
    ut = {"antal": antal, "vinnare": vinnare, "vinnarodds": vinnarodds,
          "startmetod": "auto" if str((lopp or {}).get("startMethod", "")).startswith("auto") else "volt"}
    vunnen = r["status"] == "vunnen"
    if typ in ("Vinnare", "Plats"):
        nr = int(r["val"])
        s = starts.get(nr, {})
        fo, galopp, disk = _plac(s)
        slut = (s.get("result") or {}).get("finalOdds")
        ut.update({"placering": fo or None, "slutodds": slut, "rorelse": ror.get((r["lopp_id"], nr))})
        if typ == "Vinnare" and slut and r["odds"] and float(r["odds"]) > 1:
            ut["clv"] = math.log(float(r["odds"]) / float(slut))   # > 0: oddset sjönk efter spelet (bra tecken)
        k = 1 if typ == "Vinnare" else config.plats_antal(antal) or 3
        if s.get("scratched"):
            orsak = "struken"
        elif vunnen:
            orsak = "vann"
        elif disk or not fo or (galopp and fo > k):
            orsak = "galopp_disk"
        elif typ == "Vinnare" and slut and r["odds"] and float(slut) > 1.25 * float(r["odds"]):
            orsak = "oddsen_steg"
        elif fo <= k + 1:
            orsak = "nara"
        elif fo > max(antal * 0.6, k + 2):
            orsak = "langt_efter"
        elif vinnarodds and vinnarodds >= 20:
            orsak = "skrall"
        else:
            orsak = "mitten"
        ut["orsak"] = orsak
        return ut
    # Trio / Tvilling
    mina = [int(x) for x in str(r["val"]).split("-")]
    djup = len(mina)
    topp = [ordning.get(i) for i in range(1, djup + 1)]
    ratt = len(set(mina) & set(t for t in topp if t))
    ut.update({"ratt_delar": ratt, "delar": djup})
    if vunnen:
        ut["orsak"] = "vann"
    elif ratt == djup - 1:
        ut["orsak"] = "nara"
    elif vinnarodds and vinnarodds >= 20 and vinnare not in mina:
        ut["orsak"] = "skrall"
    else:
        ut["orsak"] = "langt_efter" if ratt == 0 else "mitten"
    return ut


def _analysera_system(r, spel):
    avd = [set(int(x) for x in a.split(",")) for a in str(r["val"]).split("/")]
    ratt, skrallar = 0, 0
    for lopp, valda in zip(spel.get("races", []), avd):
        vinn = [s for s in lopp.get("starts", []) if (s.get("result") or {}).get("place") == 1]
        if vinn and vinn[0]["number"] in valda:
            ratt += 1
        elif vinn and ((vinn[0].get("result") or {}).get("finalOdds") or 0) >= 15:
            skrallar += 1
    fel = len(avd) - ratt
    orsak = "vann" if r["status"] == "vunnen" else ("en_avd_fel" if fel == 1 else
                                                      "skrall" if skrallar and skrallar == fel else "flera_avd_fel")
    return {"ratt_delar": ratt, "delar": len(avd), "orsak": orsak}


def _rader_att_analysera(data_dir):
    """Avgjorda spel från huvudboten och arenan, med en unik nyckel."""
    d = Path(data_dir)
    delar = []
    if (d / "papperspel.csv").exists():
        p = pd.read_csv(d / "papperspel.csv", dtype={"val": str})
        p["kalla"] = "huvud"
        delar.append(p)
    if (d / "arena.csv").exists():
        a = pd.read_csv(d / "arena.csv")
        if not a.empty:
            a = a.assign(kalla="arena:" + a.bot.astype(str), typ="Vinnare", val=a.nr.astype(int).astype(str))
            delar.append(a)
    if not delar:
        return pd.DataFrame()
    df = pd.concat(delar, ignore_index=True)
    df = df[df.status.isin(["vunnen", "förlorad"])].copy()
    df["lopp_id"] = df["lopp_id"].fillna("").astype(str)
    df["nyckel"] = df.kalla + "|" + df.spel_id.astype(str) + "|" + df.typ.astype(str) + "|" + df.val.astype(str)
    return df


def las_analys(data_dir="data"):
    f = Path(data_dir) / ANALYSFIL
    return pd.read_csv(f) if f.exists() else pd.DataFrame(columns=KOLUMNER)


def uppdatera(klient, data_dir="data", max_lopp=MAX_NYA_LOPP):
    """Analysera nya avgjorda spel. Returnerar antal nya rader."""
    alla = _rader_att_analysera(data_dir)
    if alla.empty:
        return 0
    gamla = las_analys(data_dir)
    nya = alla[~alla.nyckel.isin(set(gamla.nyckel))]
    if nya.empty:
        return 0
    rf = Path(data_dir) / "rorelse.csv"
    ror = {}
    if rf.exists():
        rr = pd.read_csv(rf).drop_duplicates(["lopp_id", "nr"], keep="last")
        ror = {(a, int(b)): float(c) for a, b, c in zip(rr.lopp_id, rr.nr, rr.rorelse)}
    systemtyper = set(config.SYSTEMSPEL)
    hamtade, rader = {}, []
    for _, r in nya.iterrows():
        typ = str(r["typ"]).split("-")[0]
        sid = str(r["spel_id"]) if typ in systemtyper else f"vinnare_{r['lopp_id']}"
        if sid not in hamtade:
            if len(hamtade) >= max_lopp:
                continue
            try:
                hamtade[sid] = klient.spel(sid)
            except Exception as e:                    # en trasig sida ska inte stoppa resten
                print(f"  (förlustanalys: kunde inte hämta {sid}: {e})")
                hamtade[sid] = None
        spel = hamtade[sid]
        if not spel or spel.get("status") != "results":
            continue
        try:
            extra = _analysera_system(r, spel) if typ in systemtyper else _analysera_lopp_spel(r, spel, ror)
        except Exception as e:
            print(f"  (förlustanalys {r['nyckel']}: {e})")
            continue
        if not extra:
            continue
        mc = marknadschans(r["typ"], r["odds"])
        chans = float(r["chans"]) if pd.notna(r["chans"]) else None
        rader.append({**{k: r.get(k) for k in ("nyckel", "kalla", "skapad", "spel_id", "lopp_id", "typ", "val",
                                                "insats", "odds", "chans", "status", "utbetalning")},
                      "marknadschans": mc, "kvot": (chans / mc) if (chans and mc) else None, **extra})
    if rader:
        f = Path(data_dir) / ANALYSFIL
        ut = pd.DataFrame(rader).reindex(columns=KOLUMNER)
        for k in ("chans", "marknadschans", "kvot", "clv", "rorelse"):
            ut[k] = pd.to_numeric(ut[k], errors="coerce").round(5)
        ut.to_csv(f, mode="a", header=not f.exists(), index=False)
    return len(rader)


# ---------------- 2. lärdomar ----------------
def _grupp_matt(g):
    """Träffar mot förväntat i en grupp. z > 0: träffar oftare än boten trodde."""
    g = g.dropna(subset=["chans"])
    n = len(g)
    if n == 0:
        return None
    p = g.chans.clip(0.0005, 0.9995)
    traff = int((g.status == "vunnen").sum())
    forv = float(p.sum())
    var = float((p * (1 - p)).sum())
    z = (traff - forv) / math.sqrt(var) if var > 0 else 0.0
    ins = float(g.insats.sum())
    clv = g.clv.dropna() if "clv" in g else pd.Series(dtype=float)
    return {"spel": n, "traffar": traff, "forvantat": round(forv, 2), "z": round(z, 2),
            "roi": round((float(g.utbetalning.sum()) - ins) / ins, 4) if ins else None,
            "clv": round(float(clv.mean()), 4) if len(clv) >= 10 else None, "clv_n": int(len(clv))}


def _grupperingar(df):
    """(rubrik, nyckelfunktion) – sätt att dela upp spelen på."""
    return [
        ("Speltyp", lambda d: d.typ.astype(str)),
        ("Oddsnivå", lambda d: d.marknadschans.map(band)),
        ("Hur mycket boten trodde mer än marknaden", lambda d: d.kvot.map(kvotband)),
        ("Oddsrörelse före spelet", lambda d: d.rorelse.map(lambda x: None if pd.isna(x) else
                                                           "nedspelad" if x >= 0.10 else "uppspelad" if x <= -0.10 else "stilla")),
        ("Startmetod", lambda d: d.startmetod),
        ("Antal startande", lambda d: d.antal.map(lambda x: None if pd.isna(x) else
                                                  "≤ 8" if x <= 8 else "9–12" if x <= 12 else "13+")),
        ("Speltyp × oddsnivå", lambda d: d.typ.astype(str) + " · " + d.marknadschans.map(band).fillna("?")),
    ]


def _text_lardom(rubrik, grupp, m, kalla):
    vem = "Huvudboten" if kalla == "huvud" else f"Arenans bot '{kalla.split(':', 1)[1]}'"
    if m["z"] < 0:
        return (f"{vem} överskattar sina chanser för {rubrik.lower()} = {grupp}: "
                f"{m['traffar']} träffar på {m['spel']} spel, men den räknade med {m['forvantat']:.1f}.")
    return (f"{vem} underskattar sina chanser för {rubrik.lower()} = {grupp}: "
            f"{m['traffar']} träffar på {m['spel']} spel, den räknade bara med {m['forvantat']:.1f}.")


def berakna(data_dir="data"):
    """Räknar fram lärdomar, förlustorsaker och försiktighetsfaktorer. Sparar data/lardomar.json."""
    df = las_analys(data_dir)
    ut = {"spel": int(len(df)), "lardomar": [], "testade_grupper": 0, "orsaker": {}, "forsiktighet": {},
          "clv": {}, "kalibrering": [], "senaste_forluster": []}
    if not df.empty:
        for k in ("chans", "marknadschans", "kvot", "clv", "rorelse", "antal", "insats", "utbetalning"):
            df[k] = pd.to_numeric(df[k], errors="coerce")
        # Förlustorsaker per källa
        forl = df[df.status == "förlorad"]
        for kalla, g in forl.groupby("kalla"):
            ut["orsaker"][kalla] = {ORSAKER.get(o, o): int(n) for o, n in g.orsak.value_counts().items()}
        # Lärdomar: bara statistiskt tydliga skillnader
        for kalla, g in df.groupby("kalla"):
            for rubrik, fn in _grupperingar(g):
                nycklar = fn(g)
                for grupp, gg in g.groupby(nycklar):
                    if grupp is None or len(gg) < MIN_SPEL_LARDOM:
                        continue
                    m = _grupp_matt(gg)
                    if not m:
                        continue
                    ut["testade_grupper"] += 1
                    if abs(m["z"]) >= Z_LARDOM:
                        ut["lardomar"].append({"kalla": kalla, "rubrik": rubrik, "grupp": str(grupp), **m,
                                               "text": _text_lardom(rubrik, grupp, m, kalla)})
        ut["lardomar"].sort(key=lambda x: -abs(x["z"]))
        # Slutodds-mått (CLV) per källa: snabbaste måttet på om man slår marknaden
        for kalla, g in df.groupby("kalla"):
            c = g.clv.dropna()
            if len(c) >= 10:
                ut["clv"][kalla] = {"spel": int(len(c)), "snitt": round(float(c.mean()), 4),
                                    "se": round(float(c.std(ddof=1) / math.sqrt(len(c))), 4),
                                    "andel_battre": round(float((c > 0).mean()), 3)}
        # Försiktighet för huvudbotens speltyper
        h = df[df.kalla == "huvud"]
        for typ, g in h.groupby("typ"):
            m = _grupp_matt(g)
            if not m or m["spel"] < MIN_SPEL_FORSIKTIG:
                continue
            faktor = (m["traffar"] + PRIOR_TRAFFAR) / (m["forvantat"] + PRIOR_TRAFFAR)
            faktor = float(min(1.0, max(MIN_FAKTOR, faktor)))
            if faktor < 0.995:
                ut["forsiktighet"][str(typ)] = {"faktor": round(faktor, 3), **m}
        # Kalibrering för huvudbotens spel: sa boten X %, hur ofta blev det rätt?
        hh = h.dropna(subset=["chans"])
        if len(hh) >= 20:
            gr = pd.cut(hh.chans, [0, 0.03, 0.07, 0.15, 0.3, 1])
            for iv, g in hh.groupby(gr, observed=True):
                if len(g) >= 5:
                    ut["kalibrering"].append({"grupp": f"{iv.left*100:.0f}–{iv.right*100:.0f} %", "spel": int(len(g)),
                                              "trodde": round(float(g.chans.mean()), 4),
                                              "blev": round(float((g.status == "vunnen").mean()), 4)})
        # Senaste förlorade spel med orsak (för appen)
        sen = forl[forl.kalla == "huvud"].sort_values("skapad").tail(12)
        ut["senaste_forluster"] = [{"skapad": str(r.skapad), "typ": str(r.typ), "val": str(r.val),
                                    "odds": None if pd.isna(r.odds) else float(r.odds),
                                    "chans": None if pd.isna(r.chans) else float(r.chans),
                                    "placering": None if pd.isna(r.placering) else int(r.placering),
                                    "vinnare": None if pd.isna(r.vinnare) else int(r.vinnare),
                                    "orsak": ORSAKER.get(r.orsak, r.orsak)} for r in sen.itertuples()][::-1]
    f = Path(data_dir) / LARDOMSFIL
    f.write_text(json.dumps(ut, ensure_ascii=False, indent=1), encoding="utf-8")
    return ut


def las_lardomar(data_dir="data"):
    f = Path(data_dir) / LARDOMSFIL
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


# ---------------- 3. försiktighet i spelbesluten ----------------
def forsiktighet(data_dir="data"):
    """{speltyp: faktor} där faktor < 1 sänker botens chans (bara åt det försiktiga hållet)."""
    return {t: v["faktor"] for t, v in (las_lardomar(data_dir).get("forsiktighet") or {}).items()}


def justera_spel(spel, faktorer, bank):
    """Sänk chansen för speltyper där boten visat sig överskatta sig. Spel som inte längre har
    tillräckligt övervärde tas bort; Vinnare/Plats får ny Kelly-insats."""
    if not faktorer:
        return spel
    import strategy
    ut = []
    for s in spel:
        f = faktorer.get(s["typ"])
        if f is None or f >= 1:
            ut.append(s)
            continue
        chans = s["chans"] * f
        ev = chans * s["odds"] - 1
        min_ev = config.KORSPOOL_OVERVARDE if s["typ"].endswith("-pool") else config.MIN_OVERVARDE
        if ev < min_ev:
            continue
        s = {**s, "chans": chans, "overvarde": ev, "forsiktighet": f}
        if s["typ"] in ("Vinnare", "Plats", "Plats-pool"):
            s["insats"] = strategy.kelly_insats(chans, s["odds"], bank)
            if s["insats"] <= 0:
                continue
        ut.append(s)
    return ut


def kor(klient, data_dir="data"):
    """Uppdatera analysen och lärdomarna. Returnerar (nya rader, lärdomar)."""
    n = uppdatera(klient, data_dir)
    return n, berakna(data_dir)
