"""
Inställningar för ATG-boten. Ändra gärna här – allt är förklarat.
Siffror markerade KONTROLLERA bör du dubbelkolla på atg.se (spelregler ändras ibland).
"""

# ---- Pengar (låtsaspengar i pappersläget) ----
BANKRULLE_START = 1000          # kr du "låtsas" börja med
KELLY_ANDEL = 0.25              # hur stor del av Kelly-insatsen vi vågar (0.25 = försiktigt)
MAX_INSATS_ANDEL = 0.03         # aldrig mer än 3 % av bankrullen på ett enskilt spel
MIN_INSATS = 10                 # ATG:s minsta insats på Vinnare/Plats (KONTROLLERA)
MAX_SYSTEM_ANDEL = 0.05         # max 5 % av bankrullen per V-system i pappersspelet
MAX_FORLUST_PER_VECKA = 300     # stoppregel: boten slutar föreslå spel om du förlorat mer än så på 7 dagar

# ---- När är ett spel "värt" det? ----
MIN_OVERVARDE = 0.10            # spela bara om förväntat värde är minst +10 % (p * odds - 1 >= 0.10)
MIN_OMSATTNING = 50000          # kr i vinnarpoolen innan boten litar på oddsen (tidiga odds är brus)
MIN_SANNOLIKHET = 0.04          # ignorera hästar som modellen ger under 4 % chans (för osäkert)

# ---- Automatläget (GitHub) ----
SPELFONSTER_MIN = 14            # pappersspela lopp som startar inom så många minuter
SYSTEM_BUDGET = 200             # kr per V-system i automatläget
SPELA_FORE_MIN = 3              # vaktläget spelar när det är så här många minuter kvar (eller mindre)
ODDSLOGG_FRAN_MIN = 30          # börja logga odds varje minut så här långt före start
SYSTEM_BARA_JACKPOTT = True     # pappersspela bara V-system på jackpottomgångar (annars är avdraget för stort)
KORSPOOL_OVERVARDE = 0.15       # korspool-spel kräver minst +15 % enligt marknadens egna vinnarodds
NOTIS_OVERVARDE = 0.30          # skicka mobilnotis när ett spel har minst +30 % övervärde
AI_MODELL = "claude-haiku-5-5"  # billig och snabb modell för att läsa ATG:s kommentarer

# ---- Vinstavdrag (den del ATG/staten behåller) ----
AVDRAG = {
    "vinnare": 0.15, "plats": 0.15,         # 85 % återbetalning
    "tvilling": 0.20, "trio": 0.20,         # KONTROLLERA
    "V85": 0.35, "V86": 0.35, "V64": 0.35, "V65": 0.35,
    "GS75": 0.35, "V75": 0.35, "V5": 0.35, "V4": 0.35, "V3": 0.35, "dd": 0.25, "ld": 0.25,  # KONTROLLERA
}   # OBS: boten använder hellre ATG:s egen siffra (returnToPlayer) när den finns

# ---- Radpris för systemspel (kr per rad) KONTROLLERA ----
RADPRIS = {"V85": 0.5, "V86": 0.25, "V64": 1.0, "V65": 1.0, "GS75": 1.0, "V75": 0.5,
           "V5": 0.5, "V4": 1.0, "V3": 1.0, "dd": 5.0, "ld": 5.0}

# ---- Vilka spel boten samlar data från och ger tips på ----
SYSTEMSPEL = ["V85", "V86", "V64", "V65", "GS75", "V75", "V5", "V4", "V3", "dd", "ld"]
LOPPSPEL = ["vinnare", "plats", "trio", "tvilling"]
LANDER = ["SE"]                 # bara svenska banor som standard (lägg till "NO", "FI" om du vill)
SPORT = "trot"                  # "trot" = trav, "gallop" = galopp. Modellen är byggd för trav.

# ---- Plats: hur många placeringar som betalas (KONTROLLERA) ----
def plats_antal(antal_startande: int) -> int:
    if antal_startande >= 8:
        return 3
    if antal_startande >= 5:
        return 2
    return 0  # inget platsspel

# ---- Teknik ----
PAUS_MELLAN_ANROP = 0.6         # sekunder mellan anrop till ATG – var snäll mot deras server
L2_STRAFF = 1.0                 # hur hårt modellen hålls tillbaka från att överanpassa
