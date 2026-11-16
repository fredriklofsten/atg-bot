"""
Botens hjärna: en "betingad logit"-modell (samma grundidé som Bill Benter använde i Hongkong).

Steg 1 – Fundamental modell: lär sig hur mycket varje egenskap (spår, kusk, form ...)
         påverkar chansen att vinna, jämfört med de andra hästarna i SAMMA lopp.
Steg 2 – Kombination: blandar steg 1 med marknadens odds. Marknaden vet mycket,
         så vi låter datan avgöra hur mycket vi ska lita på oss själva.

Resultat: en vinstchans per häst som summerar till 100 % i varje lopp.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

import config
from features import FEATURES, FORHANDSVIKT, forbered_X


MIN_LOPP_EGEN_VIKT = 300   # så många lopp med data krävs innan modellen själv väger in en ny signal

# ---------------- matematiken ----------------
def _grupper(lopp_ids):
    """Index där varje nytt lopp börjar (datan måste vara sorterad på lopp)."""
    lopp_ids = np.asarray(lopp_ids)
    start = np.r_[0, np.flatnonzero(lopp_ids[1:] != lopp_ids[:-1]) + 1]
    return start


def softmax_per_lopp(poang, start):
    mx = np.maximum.reduceat(poang, start)
    langd = np.diff(np.r_[start, len(poang)])
    e = np.exp(poang - np.repeat(mx, langd))
    summa = np.add.reduceat(e, start)
    return e / np.repeat(summa, langd)


def anpassa_logit(X, y, start, l2):
    """Hitta vikter w som maximerar sannolikheten för de faktiska vinnarna."""
    def kostnad(w):
        p = softmax_per_lopp(X @ w, start)
        ll = np.sum(np.log(np.clip(p[y == 1], 1e-12, None)))
        grad = -(X.T @ (y - p)) + 2 * l2 * w
        return -ll + l2 * w @ w, grad
    res = minimize(kostnad, np.zeros(X.shape[1]), jac=True, method="L-BFGS-B")
    return res.x


def rena_lopp(df):
    """Behåll bara lopp med exakt en vinnare och minst 4 hästar."""
    df = df.dropna(subset=["vann"])
    ok = df.groupby("lopp_id")["vann"].transform("sum") == 1
    ok &= df.groupby("lopp_id")["nr"].transform("count") >= 4
    return df[ok].sort_values(["datum", "lopp_id", "nr"]).reset_index(drop=True)


def marknads_p(df):
    """Marknadens sannolikhet ur vinnaroddsen (normaliserad till 100 % per lopp).
    Saknas odds används streckprocent."""
    odds = pd.to_numeric(df["odds"], errors="coerce")
    inv = 1 / odds.where((odds > 1) & (odds < 99.9))   # 99.99 = "inga pengar på hästen ännu"
    if "streck" in df:
        inv = inv.fillna(pd.to_numeric(df["streck"], errors="coerce") / 100)
    inv = inv.fillna(inv.groupby(df["lopp_id"]).transform("min")).fillna(0.01).clip(lower=0.002)
    return (inv / inv.groupby(df["lopp_id"]).transform("sum")).astype(float)


# ---------------- modellen ----------------
class Modell:
    def __init__(self):
        self.w1 = None
        self.w2 = None
        self.medel = None
        self.std = None
        self.antal_med = {}     # hur många lopp som har data för de nya egenskaperna
        self.l2 = config.L2_STRAFF
        self.avstangda = []     # egenskaper som AI-forskaren stängt av

    def _maskera(self, df):
        if not self.avstangda:
            return df
        df = df.copy()
        for c in self.avstangda:
            df[c] = 0.0
        return df

    def features_namn(self):
        return list(FEATURES)

    def p_fundamental(self, df):
        X, _, _ = forbered_X(self._maskera(df), self.medel, self.std)
        return softmax_per_lopp(X @ self.w1, _grupper(df["lopp_id"].values))

    def forklara(self, df, antal=3):
        """Varför tror boten som den gör? Per häst: egenskaperna som drar mest upp/ner jämfört med
        de andra hästarna i loppet. Returnerar lista (en per rad) av [(egenskap, bidrag), ...]."""
        X, _, _ = forbered_X(self._maskera(df), self.medel, self.std)
        bidrag = X * self.w1                                   # poäng per egenskap
        start = _grupper(df["lopp_id"].values)
        langd = np.diff(np.r_[start, len(df)])
        snitt = np.repeat(np.add.reduceat(bidrag, start, axis=0) / langd[:, None], langd, axis=0)
        rel = bidrag - snitt                                   # jämfört med de andra i loppet
        xsnitt = np.repeat(np.add.reduceat(X, start, axis=0) / langd[:, None], langd, axis=0)
        hog = X - xsnitt                                       # >0: hästen har högre värde än fältet
        ut = []
        for rad, h in zip(rel, hog):
            ordning = np.argsort(-np.abs(rad))
            ut.append([(FEATURES[j], float(rad[j]), 1 if h[j] > 0 else -1)
                       for j in ordning[:antal] if abs(rad[j]) >= 0.12])
        return ut

    def p_slutlig(self, df):
        """Botens vinstchans per häst. df måste vara sorterad på lopp_id."""
        pf = self.p_fundamental(df)
        pm = marknads_p(df).values
        Z = np.c_[np.log(np.clip(pf, 1e-6, None)), np.log(np.clip(pm, 1e-6, None))]
        poang = Z @ self.w2
        # Nya signaler utan tillräcklig historik: försiktig förhandsvikt tills modellen lärt sig själv
        for f, vikt in FORHANDSVIKT.items():
            if self.antal_med.get(f, 0) < MIN_LOPP_EGEN_VIKT and f in df:
                poang = poang + vikt * pd.to_numeric(df[f], errors="coerce").fillna(0).values
        return softmax_per_lopp(poang, _grupper(df["lopp_id"].values))

    def trana(self, df, visa=True):
        df = rena_lopp(df)
        for c in FEATURES:
            if c not in df:
                df[c] = np.nan if c not in ("rorelse_saknas", "ai_saknas", "vila_saknas") else 1
        self.antal_med = {f: int(df.loc[df[f + "_saknas"] == 0, "lopp_id"].nunique()) if f + "_saknas" in df else 0
                          for f in FORHANDSVIKT}
        lopp = df["lopp_id"].unique()
        if len(lopp) < 200:
            print(f"OBS: bara {len(lopp)} lopp. Modellen blir bättre med 2000+ lopp (kör 'samla' fler dagar).")
        # Tidsordning: lär på det gamla, testa på det nya (som i verkligheten)
        n1, n2 = int(len(lopp) * 0.6), int(len(lopp) * 0.8)
        del1 = df[df.lopp_id.isin(lopp[:n1])]
        del2 = df[df.lopp_id.isin(lopp[n1:n2])]
        test = df[df.lopp_id.isin(lopp[n2:])]

        X1, self.medel, self.std = forbered_X(self._maskera(del1))
        self.w1 = anpassa_logit(X1, del1["vann"].values, _grupper(del1["lopp_id"].values), self.l2)

        pf2 = self.p_fundamental(del2)
        Z2 = np.c_[np.log(pf2), np.log(marknads_p(del2).values)]
        self.w2 = anpassa_logit(Z2, del2["vann"].values, _grupper(del2["lopp_id"].values), 0.01)

        rapport = self.utvardera(test)
        # Träna om steg 1 på allt utom testet så att modellen är så färsk som möjligt
        alla = df[df.lopp_id.isin(lopp[:n2])]
        Xa, self.medel, self.std = forbered_X(self._maskera(alla))
        self.w1 = anpassa_logit(Xa, alla["vann"].values, _grupper(alla["lopp_id"].values), self.l2)
        rapport["antal_lopp"] = int(len(lopp))
        if visa:
            skriv_rapport(rapport, self)
        return rapport

    def utvardera(self, test):
        y = test["vann"].values == 1
        pm = marknads_p(test).values
        pf = self.p_fundamental(test)
        ps = self.p_slutlig(test)
        r = {
            "testlopp": int(test["lopp_id"].nunique()),
            "loglik_marknad": float(np.mean(np.log(pm[y]))),
            "loglik_fundamental": float(np.mean(np.log(pf[y]))),
            "loglik_bot": float(np.mean(np.log(ps[y]))),
        }
        # Simulera: spela 10 kr Vinnare där boten ser övervärde (slutodds)
        odds = test["odds"].values
        ev = ps * odds - 1
        for troskel in (0.0, 0.1, 0.2, 0.3):
            spel = (ev > troskel) & (ps >= config.MIN_SANNOLIKHET) & np.isfinite(odds)
            insats = 10 * spel.sum()
            vinst = 10 * (odds * (spel & y)).sum()
            r[f"sim_{int(troskel*100)}"] = {"spel": int(spel.sum()), "insats": float(insats),
                                           "tillbaka": float(vinst),
                                           "roi": float((vinst - insats) / insats) if insats else 0.0}
        return r

    def spara(self, fil="models/modell.json"):
        Path(fil).parent.mkdir(parents=True, exist_ok=True)
        Path(fil).write_text(json.dumps({
            "features": FEATURES, "w1": list(self.w1), "w2": list(self.w2),
            "medel": self.medel.to_dict(), "std": self.std.to_dict(), "antal_med": self.antal_med,
            "l2": self.l2, "avstangda": self.avstangda},
            indent=1), encoding="utf-8")

    @classmethod
    def ladda(cls, fil="models/modell.json"):
        d = json.loads(Path(fil).read_text(encoding="utf-8"))
        m = cls()
        if d["features"] != FEATURES:
            raise SystemExit("Modellen är tränad med andra egenskaper – kör 'python bot.py trana' igen.")
        m.w1, m.w2 = np.array(d["w1"]), np.array(d["w2"])
        m.medel, m.std = pd.Series(d["medel"]), pd.Series(d["std"])
        m.antal_med = d.get("antal_med", {})
        m.l2, m.avstangda = d.get("l2", config.L2_STRAFF), d.get("avstangda", [])
        return m


def skriv_rapport(r, m):
    print(f"\n=== Träningsrapport ({r['testlopp']} testlopp som modellen aldrig sett) ===")
    print("Hur bra gissar vi vinnaren? (högre = bättre, närmare 0)")
    print(f"  Marknaden (oddsen):       {r['loglik_marknad']:.4f}")
    print(f"  Bara egen analys:          {r['loglik_fundamental']:.4f}")
    print(f"  Boten (egen + marknad):    {r['loglik_bot']:.4f}")
    if r["loglik_bot"] > r["loglik_marknad"]:
        print("  -> Boten slår marknaden en aning. Bra tecken, men kräver mer test.")
    else:
        print("  -> Boten slår INTE marknaden ännu. Samla mer data innan du litar på den.")
    print("\nSimulerat Vinnare-spel, 10 kr per spel, på slutodds:")
    for k in ("sim_0", "sim_10", "sim_20", "sim_30"):
        s = r[k]
        print(f"  övervärde > {k[4:]:>2} %: {s['spel']:5d} spel, insats {s['insats']:8.0f} kr, "
              f"tillbaka {s['tillbaka']:8.0f} kr, ROI {s['roi']*100:+.1f} %")
    print("  VARNING: simuleringen använder slutoddsen, som du inte vet när du spelar. Sena pengar")
    print("  ändrar oddsen och din egen insats sänker dem. Verkligheten blir sämre – lita på pappersspelet.")
    print("\nVad modellen lärt sig (positivt = ökar vinstchansen):")
    vikter = sorted(zip(FEATURES, m.w1), key=lambda t: -abs(t[1]))
    for namn, w in vikter[:12]:
        print(f"  {namn:20s} {w:+.3f}")
    print(f"  Blandning: egen analys {m.w2[0]:.2f}, marknad {m.w2[1]:.2f}")
