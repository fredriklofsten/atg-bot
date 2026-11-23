"""
ATG-boten – styr allt härifrån.

  python bot.py samla --dagar 60      hämta historik (resultat, odds, statistik) från ATG
  python bot.py trana                 lär modellen av historiken och visa hur bra den är
  python bot.py tips                  dagens förslag (V-spel, Vinnare/Plats, Trio/Tvilling)
  python bot.py tips --spara          ... och lägg förslagen som pappersspel (låtsaspengar)
  python bot.py ratta                 rätta pappersspelen när loppen är klara
  python bot.py saldo                 hur går det för boten?
  python bot.py utforska V85_2026-11-14_14_5   titta i rådata för ett spel
  python bot.py automat               (GitHub) en runda: rätta, spela lopp som snart startar, bygg appen
  python bot.py vakt --timmar 4.5     (GitHub) vaktar i flera timmar: odds varje minut, spel 1–3 min före start
  python bot.py app                   bygg webbappen docs/index.html
  python bot.py arena                 ställningen mellan arenans bottar
  python bot.py arena-trana           träna arenans modellvarianter
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import config
import motor
from atg_api import ATGKlient, lopp_i_kalender, spel_i_kalender
from features import bygg_dataset
from model import Modell
from papper import Papperskassa

DATA = "data"
MODELL_FIL = "models/modell.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # så att å, ä, ö syns i Windows


def pct(x):
    return f"{x*100:4.1f}%"


# ------------------------------------------------------------------
def cmd_samla(a):
    slut = date.today() - timedelta(days=1)
    dagar = [(slut - timedelta(days=i)).isoformat() for i in range(a.dagar)][::-1]
    print(f"Hämtar {len(dagar)} dagar ({dagar[0]} – {dagar[-1]}). Redan hämtade dagar går snabbt.")
    df = bygg_dataset(dagar, DATA)
    print(f"\nKlart! Databasen har nu {df['lopp_id'].nunique()} lopp och {len(df)} hästar.")
    print("Nästa steg: python bot.py trana")


def cmd_trana(a):
    fil = Path(DATA) / "dataset.csv"
    if not fil.exists():
        sys.exit("Ingen data ännu. Kör först: python bot.py samla --dagar 60")
    df = pd.read_csv(fil, low_memory=False)
    import forskare
    inst = forskare.las_installningar()
    m = Modell()
    m.l2, m.avstangda = inst.get("l2", config.L2_STRAFF), inst.get("avstangda", [])
    rapport = m.trana(df)
    m.spara(MODELL_FIL)
    import json
    rapport["datum"] = date.today().isoformat()
    rapport["vikter"] = dict(zip(m.features_namn(), [float(w) for w in m.w1]))
    rapport["blandning"] = [float(m.w2[0]), float(m.w2[1])]
    Path("models/rapport.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = Path(DATA) / "rapporthistorik.json"
    h = json.loads(hist.read_text(encoding="utf-8")) if hist.exists() else []
    h = [x for x in h if x.get("datum") != rapport["datum"]] + [{k: rapport[k] for k in (
        "datum", "antal_lopp", "testlopp", "loglik_marknad", "loglik_bot", "loglik_fundamental")}]
    hist.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nModellen sparad i {MODELL_FIL}. Nästa steg: python bot.py tips")


def _visa_system(an, ut):
    ut.append(f"## {an['typ']} – {an['bana']} (start {str(an['start'])[11:16]}, avdrag {an['avdrag']*100:.0f} %)")
    if not an["odds_oppna"]:
        ut.append("_Tidigt läge: för lite pengar i vinnarpoolerna, så chanserna bygger på streck + egen analys. "
                  "Kör igen närmare start._")
    for a in an["avdelningar"]:
        rad = ", ".join(f"{h['nr']} {h['hast'][:14]} {pct(h['p'])} (streck {pct(h['streck'])})" for h in a["hastar"][:4])
        ut.append(f"Avd {a['avd']}: {rad}{'  <- SPIKKANDIDAT' if a['spik'] else ''}")
    ut.append("")
    for namn, sy in an["system"].items():
        ut.append(f"**{namn}** {sy['rader']} rader = {sy['kostnad']:.0f} kr | träffchans alla rätt "
                  f"{sy['traffchans']*100:.3f} % | värdeindex {sy['vardeindex']:.2f}")
        ut.append("    " + sy["val"].replace("/", " / "))
    ut.append(f"_Värdeindex över ~{an['kravs']:.2f} behövs för att gå plus i längden "
              f"(jackpot och lägre vinstnivåer ej medräknade)._\n")


def cmd_tips(a):
    if not Path(MODELL_FIL).exists():
        sys.exit("Ingen tränad modell. Kör: python bot.py samla --dagar 60  och sedan  python bot.py trana")
    modell = Modell.ladda(MODELL_FIL)
    klient = ATGKlient(DATA)
    datum = a.datum or date.today().isoformat()
    kal = klient.kalender(datum)
    if not kal:
        sys.exit(f"Kunde inte hämta ATG:s kalender för {datum}.")
    kassa = Papperskassa(DATA)
    bank = kassa.bankrulle()
    ut = [f"# ATG-botens förslag {datum}", f"Bankrulle (låtsas): {bank:.0f} kr", ""]

    if a.typ in ("alla", "system"):
        for g in spel_i_kalender(kal, config.SYSTEMSPEL):
            if g["land"] not in config.LANDER or g["sport"] != config.SPORT or g.get("status") == "results":
                continue
            an = motor.analysera_system(klient, modell, g, a.budget)
            if not an:
                continue
            _visa_system(an, ut)
            if a.spara:
                bank = motor.spara_system(kassa, an, bank)

    if a.typ in ("alla", "lopp"):
        ut.append("## Vinnare / Plats / Trio / Tvilling")
        hittat, fa_pengar = False, []
        for l in lopp_i_kalender(kal):
            if l["status"] == "results":
                continue
            an = motor.analysera_lopp(klient, modell, l, bank)
            if not an:
                continue
            if an["for_lite_pengar"]:
                fa_pengar.append(f"{l['bana']} {l['nr']} ({str(l['starttid'])[11:16]})")
                continue
            if not an["spel"]:
                continue
            hittat = True
            ut.append(f"### {l['bana']} lopp {l['nr']} ({str(l['starttid'])[11:16]})")
            for s in an["spel"]:
                ut.append(f"- **{s['typ']} {s['val']} {s['hast']}**: chans {pct(s['chans'])}, odds {s['odds']:.2f} "
                          f"(rättvist {1/s['chans']:.2f}), övervärde {s['overvarde']*100:+.0f} %, insats {s['insats']} kr")
            if a.spara:
                bank = motor.spara_lopp_spel(kassa, an, bank)
        if fa_pengar:
            ut.append(f"\nFör lite pengar i poolen än (under {config.MIN_OMSATTNING} kr), kör igen närmare start: "
                      + "; ".join(fa_pengar))
        if not hittat:
            ut.append("Inga spel med tillräckligt övervärde just nu. (Det är helt normalt – och ett bra tecken på disciplin.)")
        ut.append("\n_Odds ändras fram till start. Kör tips igen strax före loppet för färska odds._")

    if a.spara:
        kassa.spara()
        ut.append("\nPappersspel sparade. Kör `python bot.py ratta` efter loppen.")
    text = "\n".join(ut)
    print(text)
    Path("rapporter").mkdir(exist_ok=True)
    Path(f"rapporter/tips_{datum}.md").write_text(text, encoding="utf-8")


def cmd_automat(a):
    """Körs av GitHub var 10:e minut: rätta, spela lopp som snart startar, bygg appen."""
    from datetime import datetime
    import json
    import appen
    modell = Modell.ladda(MODELL_FIL)
    klient = ATGKlient(DATA)
    kassa = Papperskassa(DATA)
    print(f"Rättade {kassa.ratta()} spel.")
    idag = motor.nu().date().isoformat()
    statusfil = Path(DATA) / "idag.json"
    status = json.loads(statusfil.read_text(encoding="utf-8")) if statusfil.exists() else {}
    if status.get("datum") != idag:
        status = {"datum": idag, "lopp": {}, "system": {}}
    kal = klient.kalender(idag)
    bank = kassa.bankrulle()
    for l in lopp_i_kalender(kal):
        m = motor.minuter_kvar(l["starttid"])
        if l["status"] == "results" or m is None or not (0 < m <= 45):
            continue
        an = motor.analysera_lopp(klient, modell, l, bank)
        if not an:
            continue
        an["analyserad"] = motor.nu().strftime("%H:%M")
        status["lopp"][l["lopp_id"]] = an
        if m <= config.SPELFONSTER_MIN:
            bank = motor.spara_lopp_spel(kassa, an, bank)
            print(f"  {l['bana']} {l['nr']}: {len(an['spel'])} värdespel")
    for g in spel_i_kalender(kal, config.SYSTEMSPEL):
        if g["land"] not in config.LANDER or g["sport"] != config.SPORT or g.get("status") == "results":
            continue
        m = motor.minuter_kvar(g.get("startTime"))
        if m is None or not (0 < m <= 180):
            continue
        an = motor.analysera_system(klient, modell, g, min(config.SYSTEM_BUDGET, bank * config.MAX_SYSTEM_ANDEL))
        if not an:
            continue
        an["analyserad"] = motor.nu().strftime("%H:%M")
        status["system"][g["id"]] = an
        if m <= 20:
            bank = motor.spara_system(kassa, an, bank)
    kassa.spara()
    status["senast"] = motor.nu().strftime("%Y-%m-%d %H:%M")
    statusfil.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
    appen.bygg(DATA)
    print("Appen uppdaterad: docs/index.html")


def _git_spara(meddelande):
    """Spara och ladda upp ändringar – bara när boten körs på GitHub."""
    import os
    import subprocess
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    k = lambda *c: subprocess.run(["git", *c], capture_output=True, text=True)
    k("add", "-A")
    if k("commit", "-q", "-m", meddelande).returncode != 0:
        return
    for _ in range(3):
        k("pull", "-q", "--rebase", "-X", "theirs")
        if k("push", "-q").returncode == 0:
            return
    print("  (kunde inte ladda upp just nu – försöker igen nästa gång)")


def cmd_vakt(a):
    """Körs på GitHub i flera timmar: loggar odds varje minut och spelar strax före start."""
    import json
    import time
    from datetime import timedelta
    import appen
    from features import las_loggar
    import arena
    modell = Modell.ladda(MODELL_FIL)
    arena_modeller = arena.ladda_modeller(huvud=modell)
    klient = ATGKlient(DATA)
    kassa = Papperskassa(DATA)
    slut = motor.nu() + timedelta(hours=a.timmar)
    idag = motor.nu().date().isoformat()
    statusfil = Path(DATA) / "idag.json"
    status = json.loads(statusfil.read_text(encoding="utf-8")) if statusfil.exists() else {}
    if status.get("datum") != idag:
        status = {"datum": idag, "lopp": {}, "system": {}}
    for nyckel in ("spelat_lopp", "spelat_system", "ai_klart"):
        status.setdefault(nyckel, [])
    loggfil = Path(DATA) / "oddslogg" / f"{idag}.json"
    loggfil.parent.mkdir(parents=True, exist_ok=True)
    logg = json.loads(loggfil.read_text(encoding="utf-8")) if loggfil.exists() else {}
    kal, t_kal, t_bygg, t_analys, t_prog, t_vecka = None, 0.0, 0.0, {}, 0.0, 0.0
    progfil, veckfil = Path(DATA) / "program.json", Path(DATA) / "vecka.json"
    program = json.loads(progfil.read_text(encoding="utf-8")) if progfil.exists() else {}
    if program.get("datum") != idag:
        program = {"datum": idag, "lopp": {}}
    print(f"Vaktar till {slut:%H:%M}.")

    def logga_prognos(prog):
        f = Path(DATA) / "prognoser.csv"
        pd.DataFrame([{"datum": idag, "lopp_id": prog["lopp_id"], "nr": h["nr"], "p": round(h["p"], 5),
                       "pm": round(h["pm"], 5), "odds": h["odds"]} for h in prog["hastar"]]).to_csv(
            f, mode="a", header=not f.exists(), index=False)

    def uppdatera_resultat():
        """Fyll i vinnare för loppen boten har gjort prognos på (för grafen 'bot mot oddsen')."""
        pf, rf = Path(DATA) / "prognoser.csv", Path(DATA) / "resultat.csv"
        if not pf.exists():
            return
        klara = set(pd.read_csv(rf).lopp_id) if rf.exists() else set()
        status_lopp = {l["lopp_id"]: l for l in lopp_i_kalender(kal)}
        nya = []
        for lid in set(pd.read_csv(pf).lopp_id) - klara:
            l = status_lopp.get(lid)
            if not l or l["status"] != "results":
                continue
            sp = klient.spel(f"vinnare_{lid}", farsk=True)
            vinn = [st["number"] for lp in (sp or {}).get("races", []) for st in lp.get("starts", [])
                    if (st.get("result") or {}).get("place") == 1]
            if vinn:
                nya.append({"lopp_id": lid, "vinnare": vinn[0]})
                if lid in program["lopp"]:
                    try:
                        program["lopp"][lid] = motor.program_lopp(klient, modell, {**l}, spel=sp) or program["lopp"][lid]
                    except Exception as e:
                        print(f"  (kunde inte uppdatera {lid}: {e})")
        if nya:
            pd.DataFrame(nya).to_csv(rf, mode="a", header=not rf.exists(), index=False)

    def spara_allt(medd):
        kassa.ratta()
        try:
            arena.ratta(klient, DATA)
        except Exception as e:
            print(f"  (arenan kunde inte rättas: {e})")
        try:
            uppdatera_resultat()
        except Exception as e:
            print(f"  (resultat kunde inte uppdateras: {e})")
        try:   # förlustanalys och lärdomar (bara nya avgjorda spel hämtas)
            import analys
            n_ny, _ = analys.kor(klient, DATA)
            if n_ny:
                print(f"  förlustanalysen gick igenom {n_ny} nya spel")
        except Exception as e:
            print(f"  (förlustanalysen misslyckades: {e})")
        progfil.write_text(json.dumps(program, ensure_ascii=False), encoding="utf-8")
        status["senast"] = motor.nu().strftime("%Y-%m-%d %H:%M")
        statusfil.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
        loggfil.write_text(json.dumps(logg), encoding="utf-8")
        appen.bygg(DATA)
        _git_spara(medd)

    while motor.nu() < slut:
        t0 = time.time()
        if kal is None or t0 - t_kal > 600:
            kal = klient.kalender(idag) or kal
            t_kal = t0
        lopp = [(l, motor.minuter_kvar(l["starttid"])) for l in lopp_i_kalender(kal) if l["status"] != "results"]
        lopp = [(l, m) for l, m in lopp if m is not None and m > -3]
        vspel = [(g, motor.minuter_kvar(g.get("startTime"))) for g in spel_i_kalender(kal, config.SYSTEMSPEL)
                 if g["land"] in config.LANDER and g["sport"] == config.SPORT and g.get("status") != "results"]
        vspel = [(g, m) for g, m in vspel if m is not None and m > 0]
        if not lopp and not vspel:
            print("Inga fler lopp idag.")
            break
        bank = kassa.bankrulle()
        rorelse_alla, ai_alla = las_loggar(DATA)
        # Dagens program (alla lopp, för appen) var 20:e minut
        if t0 - t_prog > 1200:
            # max 6 lopp per minut (närmast start först) så att vaktandet aldrig blir efter
            att_gora = [l for l in sorted(lopp_i_kalender(kal), key=lambda l: l["starttid"])
                        if not (l["status"] == "results" and l["lopp_id"] in program["lopp"])]
            for l in att_gora[:6]:
                try:
                    pr = motor.program_lopp(klient, modell, l, rorelse=rorelse_alla, ai=ai_alla)
                    if pr:
                        program["lopp"][l["lopp_id"]] = pr
                except Exception as e:
                    print(f"  (program {l['lopp_id']}: {e})")
            if len(att_gora) <= 6:
                t_prog = time.time()
            t_bygg = 0 if len(att_gora) <= 6 else t_bygg
        # Veckans V-spel varannan timme
        if t0 - t_vecka > 7200:
            try:
                veckfil.write_text(json.dumps({"skapad": motor.nu().strftime("%Y-%m-%d %H:%M"),
                                               "spel": motor.veckans_vspel(klient, modell, bank)},
                                              ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                print(f"  (veckans V-spel: {e})")
            t_vecka = time.time()
        for l, m in lopp:
            lid = l["lopp_id"]
            if not (0 < m <= config.ODDSLOGG_FRAN_MIN):
                continue
            spel = klient.spel(f"vinnare_{lid}", farsk=True)
            if not spel:
                continue
            # 1) logga oddsen just nu
            for lp in spel.get("races", []):
                for st in lp.get("starts", []):
                    o = ((st.get("pools") or {}).get("vinnare") or {}).get("odds")
                    if o and not st.get("scratched"):
                        logg.setdefault(lid, {}).setdefault(str(st["number"]), []).append([round(m, 1), o / 100])
            # 2) AI-betyg en gång per lopp
            if lid not in status["ai_klart"]:
                hastar = [(st["number"], st.get("horse", {}).get("name", "")) for lp in spel.get("races", [])
                          for st in lp.get("starts", []) if not st.get("scratched")]
                betyg = motor.ai_betyg(klient, lid, hastar)
                if betyg:
                    rad = pd.DataFrame([{"lopp_id": lid, "nr": n, "ai_poang": v} for n, v in betyg.items()])
                    f = Path(DATA) / "ai_betyg.csv"
                    rad.to_csv(f, mode="a", header=not f.exists(), index=False)
                    ai_alla.update({(lid, n): float(v) for n, v in betyg.items()})
                status["ai_klart"].append(lid)
            ror = motor.rorelse_fran_logg(logg.get(lid), lid)
            rorelse_alla.update(ror)
            # 3) spela strax före start, annars analysera för appen var 5:e minut
            spela = m <= config.SPELA_FORE_MIN and lid not in status["spelat_lopp"]
            if not spela and t0 - t_analys.get(lid, 0) < 300:
                continue
            an = motor.analysera_lopp(klient, modell, l, bank, ror, ai_alla, spel=spel)
            t_analys[lid] = t0
            if not an:
                continue
            an["analyserad"] = motor.nu().strftime("%H:%M")
            status["lopp"][lid] = an
            if spela:
                status["spelat_lopp"].append(lid)
                try:   # spara botens chans för alla hästar precis när beslutet tas (för utvecklingsgrafen)
                    prog = motor.program_lopp(klient, modell, l, spel=spel, rorelse=ror, ai=ai_alla)
                    if prog:
                        program["lopp"][lid] = prog
                        logga_prognos(prog)
                except Exception as e:
                    print(f"  (prognos {lid}: {e})")
                try:   # arenan: alla bottar bestämmer sig på samma odds som huvudboten (bara låtsasspel)
                    n_arena = arena.spela(klient, arena_modeller, l, spel, ror, ai_alla, DATA)
                    if n_arena:
                        print(f"  {l['bana']} {l['nr']}: arenan lade {n_arena} spel")
                except Exception as e:
                    print(f"  (arenan {lid}: {e})")
                if ror:   # spara rörelsen som den såg ut när beslutet togs (för träningen)
                    f = Path(DATA) / "rorelse.csv"
                    pd.DataFrame([{"lopp_id": k[0], "nr": k[1], "rorelse": v} for k, v in ror.items()]).to_csv(
                        f, mode="a", header=not f.exists(), index=False)
                if not an["for_lite_pengar"]:
                    lagda = []
                    bank = motor.spara_lopp_spel(kassa, an, bank, lagda)
                    kassa.spara()
                    print(f"  {l['bana']} {l['nr']}: {len(lagda)} spel")
                    starka = [s for s in lagda if s["overvarde"] >= config.NOTIS_OVERVARDE]
                    if starka:
                        motor.notis(f"{l['bana']} lopp {l['nr']} – {str(l['starttid'])[11:16]}",
                                    "\n".join(f"{s['typ']} {s['val']} {s['hast']} @ {s['odds']:.2f} "
                                              f"({s['overvarde']*100:+.0f} %)" for s in starka))
                t_bygg = 0   # bygg appen direkt efter spel
        for g, m in vspel:
            spela = m <= config.SPELA_FORE_MIN and g["id"] not in status["spelat_system"]
            if m > 180 or (not spela and t0 - t_analys.get(g["id"], 0) < 900):
                continue
            an = motor.analysera_system(klient, modell, g, min(config.SYSTEM_BUDGET, bank * config.MAX_SYSTEM_ANDEL), rorelse_alla, ai_alla)
            t_analys[g["id"]] = t0
            if not an:
                continue
            an["analyserad"] = motor.nu().strftime("%H:%M")
            status["system"][g["id"]] = an
            if spela:
                status["spelat_system"].append(g["id"])
                fore = len(kassa.df)
                bank = motor.spara_system(kassa, an, bank)
                kassa.spara()
                if len(kassa.df) > fore:
                    sy = an["system"]["Balanserad"]
                    motor.notis(f"{g['typ']} {g['bana']} – system lagt",
                                f"{sy['val']}  ({sy['kostnad']:.0f} kr, värdeindex {sy['vardeindex']:.2f})")
        kommande = sorted((l for l, m in lopp if m > 0), key=lambda l: l["starttid"])
        status["nasta"] = ({"bana": kommande[0]["bana"], "nr": kommande[0]["nr"], "start": kommande[0]["starttid"]}
                           if kommande else None)
        if time.time() - t_bygg > 600:
            spara_allt(f"Vakt {motor.nu():%F %H:%M}")
            t_bygg = time.time()
        motor.sov(max(5, 60 - (time.time() - t0) * motor._fart()))
    spara_allt(f"Vakt {motor.nu():%F %H:%M}")
    if not lopp_i_kalender(kal) or all(l["status"] == "results" for l in lopp_i_kalender(kal)):
        idag_spel = kassa.df[kassa.df.skapad.astype(str).str.startswith(idag)]
        r = idag_spel[idag_spel.status != "öppen"]
        if len(r):
            netto = r.utbetalning.sum() - r.insats.sum()
            motor.notis("ATG-boten – dagens resultat",
                        f"{len(r)} spel, netto {netto:+.0f} kr. Kassan: {kassa.bankrulle():.0f} kr.")


def cmd_veckotraning(a):
    """Måndagar: hämta förra veckans lopp och träna om modellen."""
    from datetime import datetime
    rapport = Path("models/rapport.json")
    if not a.tvinga and rapport.exists():
        import json
        senast = json.loads(rapport.read_text(encoding="utf-8")).get("datum", "2000-01-01")
        if (date.today() - date.fromisoformat(senast)).days < 7:
            print("Tränade senast", senast, "– hoppar över.")
            return
    a.dagar = 8
    cmd_samla(a)
    cmd_trana(a)


def cmd_forska(a):
    import forskare
    if a.steg == "planera":
        forskare.planera()
        _git_spara("AI-forskaren: veckans plan (förregistrerad)")
    else:
        forskare.kor()


def cmd_arena_trana(a):
    """Tränar arenans modellvarianter (försiktig, flexibel, färsk) på samma data som huvudmodellen."""
    import arena
    fil = Path(DATA) / "dataset.csv"
    if not fil.exists():
        sys.exit("Ingen data ännu. Kör först: python bot.py samla --dagar 60")
    print("Tränar arenans modellvarianter:")
    arena.trana_varianter(pd.read_csv(fil, low_memory=False))


def cmd_arena(a):
    """Visa ställningen i arenan i terminalen."""
    import arena
    df = arena.las(DATA)
    if df.empty:
        sys.exit("Inga arenaspel ännu. Vaktläget lägger dem strax före varje lopp.")
    tavla = arena.sammanfatta(df)
    print(f"{'Bot':16s} {'spel':>5s} {'rättade':>8s} {'ROI':>8s} {'±':>7s}  bedömning")
    for t in tavla:
        roi = f"{t['roi']*100:+.1f} %" if t["roi"] is not None else "–"
        se = f"{2*t['se']*100:.0f} %" if t["se"] is not None else "–"
        print(f"{t['ikon']} {t['namn']:13s} {t['spel']:5d} {t['rattade']:8d} {roi:>8s} {se:>7s}  {arena.dom(t, tavla)[0]}")
    print("\n± = ungefärligt slumpspann (2 standardfel). Lita inte på en bot förrän den slår både Favoriten och Slumpen över många spel.")


def cmd_app(a):
    import appen
    appen.bygg(DATA)
    print("Byggde docs/index.html")


def cmd_lardomar(a):
    """Analysera avgjorda spel (särskilt förlusterna) och visa vad boten lärt sig."""
    import analys
    kassa = Papperskassa(DATA)
    kassa.ratta()
    n, u = analys.kor(ATGKlient(DATA), DATA)
    print(f"Analyserade {n} nya spel. Totalt {u['spel']} spel i analysen, {u['testade_grupper']} grupper testade.")
    if u["lardomar"]:
        print("\nLärdomar (säkra, |z| >= 2,5):")
        for l in u["lardomar"]:
            print("  •", l["text"])
    else:
        print("\nInga säkra lärdomar ännu – skillnaderna är fortfarande inom slumpens ramar.")
    if u["forsiktighet"]:
        print("\nFörsiktighet i spelen just nu:")
        for t, v in u["forsiktighet"].items():
            print(f"  {t:12s} chansen × {v['faktor']:.2f}  ({v['traffar']} träffar, väntade {v['forvantat']:.1f})")
    for kalla, o in u["orsaker"].items():
        if kalla == "huvud":
            print("\nVarför huvudboten förlorade:")
            for orsak, n in o.items():
                print(f"  {orsak:40s} {n}")


def cmd_ratta(a):
    k = Papperskassa(DATA)
    n = k.ratta()
    print(f"Rättade {n} spel.\n")
    print(k.sammanfattning())


def cmd_saldo(a):
    print(Papperskassa(DATA).sammanfattning())


def cmd_utforska(a):
    spel = ATGKlient(DATA).spel(a.spel_id, farsk=True)
    if not spel:
        sys.exit("Hittade inget spel med det id:t.")
    print(f"{spel.get('id')}  status: {spel.get('status')}")
    for l in spel.get("races", []):
        print(f"\nLopp {l.get('number')} {l.get('name','')[:50]}  {l.get('distance')} m {l.get('startMethod')}")
        for s in l.get("starts", []):
            h = s.get("horse", {})
            print(f"  {s['number']:2d} {h.get('name','')[:20]:20s} odds {((s.get('pools') or {}).get('vinnare') or {}).get('odds')}"
                  f"  plac {(s.get('result') or {}).get('place')}{'  STRUKEN' if s.get('scratched') else ''}")


def main():
    p = argparse.ArgumentParser(description="ATG-bot (pappersspel)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("samla"); s.add_argument("--dagar", type=int, default=60); s.set_defaults(f=cmd_samla)
    s = sub.add_parser("trana"); s.set_defaults(f=cmd_trana)
    s = sub.add_parser("tips")
    s.add_argument("--datum", help="ÅÅÅÅ-MM-DD (standard: idag)")
    s.add_argument("--budget", type=float, default=200, help="max kr per V-system")
    s.add_argument("--typ", choices=["alla", "system", "lopp"], default="alla")
    s.add_argument("--spara", action="store_true", help="lägg förslagen som pappersspel")
    s.add_argument("--visa-alla", action="store_true", help="visa även troligaste trio/tvilling")
    s.set_defaults(f=cmd_tips)
    s = sub.add_parser("ratta"); s.set_defaults(f=cmd_ratta)
    s = sub.add_parser("lardomar"); s.set_defaults(f=cmd_lardomar)
    s = sub.add_parser("saldo"); s.set_defaults(f=cmd_saldo)
    s = sub.add_parser("utforska"); s.add_argument("spel_id"); s.set_defaults(f=cmd_utforska)
    s = sub.add_parser("automat"); s.set_defaults(f=cmd_automat)
    s = sub.add_parser("veckotraning"); s.add_argument("--tvinga", action="store_true"); s.set_defaults(f=cmd_veckotraning)
    s = sub.add_parser("app"); s.set_defaults(f=cmd_app)
    s = sub.add_parser("arena"); s.set_defaults(f=cmd_arena)
    s = sub.add_parser("arena-trana"); s.set_defaults(f=cmd_arena_trana)
    s = sub.add_parser("forska"); s.add_argument("steg", choices=["planera", "kor"]); s.set_defaults(f=cmd_forska)
    s = sub.add_parser("vakt"); s.add_argument("--timmar", type=float, default=4.5); s.set_defaults(f=cmd_vakt)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
