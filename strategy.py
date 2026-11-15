"""
Från vinstchanser till spelförslag.

Grundregeln: spela bara när botens chans * oddset > 1 (+ marginal).
Då betalar marknaden mer än hästen "borde" ge – det kallas övervärde (value).
"""
import itertools
import math

import numpy as np

import config

MAX_KVOT = 4.0   # tak för chans/streck – större skillnader är oftast brus, inte värde


# ---------- sannolikheter för placeringar (Harvilles formel) ----------
def ordning_sannolikheter(p, djup=3):
    """P(häst i etta, j tvåa, k trea) ur vinstchanserna. Returnerar dict {(i,j,k): p}.
    Harville med Henery/Lo-justering: för 2:a och 3:e plats "plattas" chanserna till
    (p^0.7 resp. p^0.55, kalibrerat på svenska travlopp), eftersom ren Harville överskattar favoriter på 2:a/3:e."""
    p = np.asarray(p, dtype=float)
    n = len(p)
    p2 = p ** 0.7 / np.sum(p ** 0.7)
    p3 = p ** 0.55 / np.sum(p ** 0.55)
    ut = {}
    for i in range(n):
        for j in range(n):
            if j == i:
                continue
            pij = p[i] * p2[j] / max(1 - p2[i], 1e-9)
            if djup == 2:
                ut[(i, j)] = pij
                continue
            for k in range(n):
                if k in (i, j):
                    continue
                ut[(i, j, k)] = pij * p3[k] / max(1 - p3[i] - p3[j], 1e-9)
    return ut


def topp_k(p, k):
    """Chansen att varje häst slutar topp k (för Plats)."""
    n = len(p)
    if k <= 1:
        return np.array(p)
    ut = np.zeros(n)
    for kombo, pr in ordning_sannolikheter(p, 3 if k >= 3 else 2).items():
        for h in set(kombo[:k]):
            ut[h] += pr
    return ut


def kelly_insats(p, odds, bankrulle):
    if odds <= 1:
        return 0
    f = (p * odds - 1) / (odds - 1)
    insats = bankrulle * max(f, 0) * config.KELLY_ANDEL
    insats = min(insats, bankrulle * config.MAX_INSATS_ANDEL)
    if insats < config.MIN_INSATS:
        return 0
    return int(insats // 5 * 5)


# ---------- Vinnare / Plats ----------
def vinnare_plats(lopp, p, bankrulle):
    """lopp = lista med rader (dict) för ett lopp, p = botens vinstchanser i samma ordning."""
    forslag = []
    k = config.plats_antal(len(lopp))
    pp = topp_k(p, k) if k else np.zeros(len(p))
    for r, pv, pt in zip(lopp, p, pp):
        for typ, chans, odds in (("Vinnare", pv, r.get("odds")), ("Plats", pt, r.get("plats_odds"))):
            if not odds or not math.isfinite(odds) or chans < config.MIN_SANNOLIKHET:
                continue
            ev = chans * odds - 1
            if ev >= config.MIN_OVERVARDE:
                forslag.append({"typ": typ, "nr": r["nr"], "hast": r["hast"], "chans": chans,
                                "odds": odds, "rattvist_odds": 1 / chans, "overvarde": ev,
                                "insats": kelly_insats(chans, odds, bankrulle)})
    return sorted(forslag, key=lambda f: -f["overvarde"])


# ---------- Trio / Tvilling ----------
def kombinationer(lopp, p, pool, typ, max_antal=5):
    """Jämför botens chans för varje kombination med ATG:s mest spelade kombinationer + odds."""
    nr = [r["nr"] for r in lopp]
    djup = 3 if typ == "trio" else 2
    ordn = ordning_sannolikheter(p, djup)
    chans = {}
    for kombo, pr in ordn.items():
        nyckel = tuple(nr[i] for i in kombo)
        if typ == "tvilling":
            nyckel = tuple(sorted(nyckel))
        chans[nyckel] = chans.get(nyckel, 0) + pr
    basta = sorted(chans.items(), key=lambda t: -t[1])[:max_antal]
    odds_atg = {}
    for m in (pool or {}).get("mostPlayed", []) or []:
        try:
            k = tuple(int(x) for x in str(m["starts"]).split("-"))
            odds_atg[tuple(sorted(k)) if typ == "tvilling" else k] = m["odds"] / 100
        except (KeyError, ValueError):
            continue
    varde = []
    for k, o in odds_atg.items():
        c = chans.get(k, 0)
        if c >= 0.01 and c * o - 1 >= config.MIN_OVERVARDE:
            varde.append({"kombo": k, "chans": c, "odds": o, "overvarde": c * o - 1})
    return {"troligast": [{"kombo": k, "chans": c, "rattvist_odds": 1 / c} for k, c in basta],
            "varde": sorted(varde, key=lambda v: -v["overvarde"])[:max_antal]}


# ---------- V-spel (V85, V86, V64 ...) ----------
def bygg_system(avdelningar, budget, radpris, avdrag, vardevikt=1.0, min_kvot=0.6):
    """
    avdelningar: lista av (nr-lista, p-lista, streck-lista[andel 0-1]).
    Väljer hästar så att systemet ryms i budgeten och balanserar
       träffchans  = produkt av (summa p för valda hästar)
       värdeindex  = produkt av (snitt av p/streck för valda hästar)
    värdeindex 1.0 = lika "smart" som genomsnittsspelaren. För att gå plus
    i längden krävs ungefär > 1 / (1 - avdrag), t.ex. > 1.54 vid 35 % avdrag.
    vardevikt: 0.3 = jaga träffar, 1 = balanserat, 2 = jaga skrällar/stora vinster.
    """
    val = []
    for nr, p, s in avdelningar:
        val.append([int(np.argmax(p))])

    def matt(val):
        trf, vi, rader = 1.0, 1.0, 1
        for (nr, p, s), v in zip(avdelningar, val):
            trf *= sum(p[i] for i in v)
            vi *= np.mean([min(p[i] / max(s[i], 0.01), MAX_KVOT) for i in v])
            rader *= len(v)
        return trf, vi, rader

    def mal(trf, vi):
        return math.log(max(trf, 1e-12)) + vardevikt * math.log(max(vi, 1e-12))

    while True:
        trf, vi, rader = matt(val)
        nu = mal(trf, vi)
        bast = None
        for a, (nr, p, s) in enumerate(avdelningar):
            for i in range(len(p)):
                if i in val[a] or p[i] < 0.02:
                    continue
                if p[i] / max(s[i], 0.01) < min_kvot:   # överstreckad häst – hoppa över
                    continue
                nytt = [list(v) for v in val]
                nytt[a].append(i)
                t2, v2, r2 = matt(nytt)
                if r2 * radpris > budget:
                    continue
                vinst = (mal(t2, v2) - nu) / math.log(r2 / rader)
                if vinst > 0 and (bast is None or vinst > bast[0]):
                    bast = (vinst, nytt)
        if bast is None:
            break
        val = bast[1]
    trf, vi, rader = matt(val)
    return {
        "avdelningar": [[avdelningar[a][0][i] for i in sorted(v, key=lambda i: -avdelningar[a][1][i])]
                        for a, v in enumerate(val)],
        "rader": rader, "kostnad": rader * radpris, "traffchans": trf,
        "vardeindex": vi, "forvantad_aterbetalning": (1 - avdrag) * vi,
    }
