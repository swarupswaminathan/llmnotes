# constants.py
'''
Constants and controlled vocabularies for medication standardization.
This includes canonical drug names, synonym mappings, frequency normalization.
Customize to your institution's medication naming conventions and commonly used abbreviations.
'''

# ============================================================
# Topical-med controlled vocabulary
# ============================================================

CANONICAL_TOP_DRUGS = {
    "apraclonidine",
    "artificial tears",
    "atropine",
    "autologous serum tears",
    "bacitracin/polymyxin b",
    "betaxolol",
    "bimatoprost",
    "brimonidine",
    "brimonidine/brinzolamide",
    "brimonidine/dorzolamide/timolol",
    "brimonidine/timolol",
    "brinzolamide",
    "brinzolamide/timolol",
    "bromfenac",
    "carteolol",
    "ciprofloxacin",
    "cyclopentolate",
    "cyclosporine",
    "dexamethasone",
    "dexamethasone/neomycin/polymyxin b",
    "dexamethasone/tobramycin",
    "diclofenac",
    "difluprednate",
    "dorzolamide",
    "dorzolamide/timolol",
    "erythromycin",
    "fluorometholone",
    "ketorolac",
    "latanoprost",
    "latanoprost/netarsudil",
    "latanoprost/timolol",
    "latanoprostene bunod",
    "levobunolol",
    "lifitegrast",
    "loteprednol",
    "metipranolol",
    "moxifloxacin",
    "nepafenac",
    "netarsudil",
    "ofloxacin",
    "phospholine iodide",
    "pilocarpine",
    "polymyxin",
    "prednisolone",
    "tacrolimus",
    "tafluprost",
    "timolol",
    "timolol/travoprost",
    "travoprost",

    # OTC (excluded)
    "pataday",
    "olopatadine",
    "zaditor",
    "ketotifen",
    "lumify",
    "muro",
    "muro 128",
}

TOP_DRUG_SYNONYMS = {
    # immunomodulators
    "cyclosporine": "cyclosporine",
    "cequa": "cyclosporine",
    "restasis": "cyclosporine",
    "csa": "cyclosporine",

    # prostaglandins
    "bimatoprost": "bimatoprost",
    "lumigan": "bimatoprost",
    "bim": "bimatoprost",

    "latanoprost": "latanoprost",
    "xalatan": "latanoprost",
    "xelpros": "latanoprost",
    "lx": "latanoprost",

    "tafluprost": "tafluprost",
    "zioptan": "tafluprost",
    "ziop": "tafluprost",
    "zio": "tafluprost",

    "travoprost": "travoprost",
    "travatan": "travoprost",
    "travatan z": "travoprost",
    "trav": "travoprost",
    "trz": "travoprost",
    "travz": "travoprost",

    "latanoprostene bunod": "latanoprostene bunod",
    "vyzulta": "latanoprostene bunod",
    "vyz": "latanoprostene bunod",

    # alpha adrenergic agonists
    "brimonidine": "brimonidine",
    "alphagan": "brimonidine",
    "alphagan p": "brimonidine",
    "alph" : "brimonidine",
    "agn" : "brimonidine",
    "alphp" : "brimonidine",
    "agn p" : "brimonidine",

    "apraclonidine": "apraclonidine",
    "apra" : "apraclonidine",
    "iopidine": "apraclonidine",

    # beta blockers
    "betaxolol": "betaxolol",
    "betoptic": "betaxolol",
    "betoptic s": "betaxolol",

    "carteolol": "carteolol",
    "ocupress" : "carteolol",

    "betagan": "levobunolol",
    "levobunolol": "levobunolol",

    "metipranolol": "metipranolol",

    "timolol": "timolol",
    "timolol-pf": "timolol",
    "timoptic": "timolol",
    "betimol": "timolol",
    "istalol": "timolol",

    # carbonic anhydrase inhibitors
    "brinzolamide": "brinzolamide",
    "azopt": "brinzolamide",
    "azo": "brinzolamide",
    "az": "brinzolamide",
    "brinz": "brinzolamide",

    "dorzolamide": "dorzolamide",
    "trusopt": "dorzolamide",
    "tru": "dorzolamide",
    "dorz": "dorzolamide",

    # cholinergic agonists
    "pilocarpine": "pilocarpine",
    "pilocar": "pilocarpine",
    "pilopine": "pilocarpine",
    "pilo": "pilocarpine",

    # acytlcholinesterase inhibitors
    "phospholine iodide": "phospholine iodide",
    "pi" : "phospholine iodide",

    # rho kinase inhibitors
    "netarsudil": "netarsudil",
    "rhopressa": "netarsudil",

    # anticholinergics
    "atropine": "atropine",
    "atro": "atropine",

    "cyclopentolate": "cyclopentolate",
    "cyclogyl": "cyclopentolate",

    # combination drugs
    "cosopt": "dorzolamide/timolol",
    "cosopt pf": "dorzolamide/timolol",
    "cosopt-pf": "dorzolamide/timolol PF",
    "cos": "dorzolamide/timolol",
    "dorz/tim": "dorzolamide/timolol",
    "dorzolamide timolol": "dorzolamide/timolol",
    "dorzolamide-timolol": "dorzolamide/timolol",

    "combigan": "brimonidine/timolol",
    "brimonidine timolol": "brimonidine/timolol",
    "brimonidine-timolol": "brimonidine/timolol",

    "simbrinza": "brimonidine/brinzolamide",
    "simb" : "brimonidine/brinzolamide",
    "sb" : "brimonidine/brinzolamide",
    "sz" : "brimonidine/brinzolamide",
    "brimonidine brinzolamide": "brimonidine/brinzolamide",
    "brimonidine-brinzolamide": "brimonidine/brinzolamide",

    "azarga": "brinzolamide/timolol",
    "brinzolamide timolol": "brinzolamide/timolol",
    "brinzolamide-timolol": "brinzolamide/timolol",

    "xalacom": "latanoprost/timolol",
    "latanoprost timolol": "latanoprost/timolol",
    "latanoprost-timolol": "latanoprost/timolol",

    "duotrav": "timolol/travoprost",
    "timolol travoprost": "timolol/travoprost",
    "timolol-travoprost": "timolol/travoprost",

    "ganfort": "bimatoprost/timolol",
    "bimatoprost timolol": "bimatoprost/timolol",
    "bimatoprost-timolol": "bimatoprost/timolol",

    "rocklatan": "latanoprost/netarsudil",
    "latanoprost netarsudil": "latanoprost/netarsudil",
    "latanoprost-netarsudil": "latanoprost/netarsudil",

    "tobradex": "dexamethasone/tobramycin",
    "dexamethasone/tobramycin": "dexamethasone/tobramycin",

    "maxitrol": "dexamethasone/neomycin/polymyxin b",

    "krytantek": "brimonidine/dorzolamide/timolol",

    # steroids
    "difluprednate": "difluprednate",
    "durezol": "difluprednate",
    "dur": "difluprednate",

    "fluorometholone": "fluorometholone",
    "fml": "fluorometholone",

    "loteprednol": "loteprednol",
    "lotemax": "loteprednol",
    "eysuvis": "loteprednol",

    "lifitegrast": "lifitegrast",
    "xiidra": "lifitegrast",

    "prednisolone": "prednisolone",
    "pred" : "prednisolone",
    "pred forte": "prednisolone",
    "prednisolone acetate": "prednisolone",
    "pf": "prednisolone",

    # NSAIDs
    "bromfenac": "bromfenac",
    "prolensa": "bromfenac",
    "bromday": "bromfenac",
    "brom": "bromfenac",

    "diclofenac": "diclofenac",
    "voltaren": "diclofenac",

    "ketorolac": "ketorolac",
    "acular": "ketorolac",

    "nepafenac": "nepafenac",
    "ilevro": "nepafenac",
    "nevanac": "nepafenac",

    # antibiotics 
    "bacitracin/polymyxin b": "bacitracin/polymyxin b",
    "polysporin" : "bacitracin/polymyxin b",

    "ciprofloxacin": "ciprofloxacin",
    "cipro" : "ciprofloxacin",

    "erythromycin": "erythromycin",
    "romycin" : "erythromycin",
    
    "moxifloxacin": "moxifloxacin",
    "vigamox" : "moxifloxacin",

    "ocuflox" : "ofloxacin",
    "ofloxacin" : "ofloxacin",

    "polymyxin": "polymyxin",
    "polytrim" : "polymyxin",
    "pt" : "polymyxin",
}

ARTIFICIAL_TEAR_SYNONYMS = {
    "systane": "artificial tears",
    "refresh": "artificial tears",
    "theratears": "artificial tears",
    "blink": "artificial tears",
    "genteal": "artificial tears",
    "optive": "artificial tears",
    "retaine": "artificial tears",
    "soothe": "artificial tears",
    "pfat" : "artificial tears",
    "artificial tears": "artificial tears",
}

SERUM_TEAR_PATTERNS = [
    r"\bast\b",
    r"\bserum tears?\b",
    r"\bautologous serum tears?\b",
    r"\bautologous serum eye drops?\b",
]

PROSTAGLANDINS = {
    "latanoprost",
    "bimatoprost",
    "travoprost",
    "tafluprost",
    "latanoprostene bunod",
    "latanoprost/netarsudil",
}

EXCLUDED_DRUGS = {
    "artificial tears",
    "ketotifen",
    "lumify",
    "muro",
    "muro 128",
    "olopatadine",
    "pataday",
    "zaditor",
}

NONESSENTIAL_MED_WORDS = {
    "generic",
    "ointment",
}

# ============================================================
# Oral-med controlled vocabulary
# ============================================================

CANONICAL_ORAL_DRUGS = {
    "acetazolamide",
    "methazolamide",
    "prednisone",
    "valacyclovir",
    "acyclovir",
}

ORAL_DRUG_SYNONYMS = {
    "acetazolamide": "acetazolamide",
    "diamox": "acetazolamide",
    "acz": "acetazolamide",
    "dmx": "acetazolamide",

    "methazolamide": "methazolamide",
    "neptazane" : "methazolamide",
    "mzm": "methazolamide",

    "prednisone": "prednisone",
    "po pred": "prednisone",

    "valacyclovir": "valacyclovir",
    "valtrex": "valacyclovir",

    "acyclovir": "acyclovir",
    "zovirax": "acyclovir",
}

# ============================================================
# Change normalization maps
# ============================================================

CHANGE_SYNONYMS = {
    "start": "Start",
    "add": "Start",
    "begin": "Start",
    "initiate": "Start",

    "stop": "Stop",
    "discontinue": "Stop",
    "dc": "Stop",
    "d/c": "Stop",
    "hold": "Stop",

    "increase": "Increase",
    "raise": "Increase",
    "up": "Increase",

    "decrease": "Decrease",
    "reduce": "Decrease",
    "lower": "Decrease",
    "taper": "Decrease",
}

CHANGE_PRIORITY = {
    "Start": 0,
    "Stop": 1,
    "Increase": 2,
    "Decrease": 3,
}

# ============================================================
# Common normalization maps
# ============================================================

FREQUENCY_MAP = {
    "qhs": "QHS",
    "every night": "QHS",
    "nightly": "QHS",
    "at bedtime": "QHS",
    "before bed": "QHS",
    "q nightly": "QHS",
    "qpm": "QHS",

    "daily": "daily",
    "once daily": "daily",
    "once a day": "daily",
    "qd": "daily",
    "every day": "daily",
    "qday": "daily",
    "q day": "daily",
    "every morning": "daily",
    "qam": "daily",
    "qdaily": "daily",

    "1x daily": "daily",
    "1x/day": "daily",
    "1 time/day": "daily",
    "1x a day": "daily",
    "1x per day": "daily",
    "1 time a day": "daily",
    "1 time per day": "daily",
    "1 time daily": "daily",
    "1 per day": "daily",

    "bid": "BID",
    "twice daily": "BID",
    "twice a day": "BID",
    "2/day": "BID",
    "every 12 hours": "BID",
    "q12h": "BID",

    "2x daily": "BID",
    "2x/day": "BID",
    "2 times/day": "BID",
    "2x a day": "BID",
    "2x per day": "BID",
    "2 times a day": "BID",
    "2 times per day": "BID",
    "2 times daily": "BID",
    "2 per day": "BID",
    "two times a day": "BID",


    "tid": "TID",
    "3/day": "TID",
    "every 8 hours": "TID",
    "q8h": "TID",

    "3x daily": "TID",
    "3x/day": "TID",
    "3 times/day": "TID",
    "3x a day": "TID",
    "3x per day": "TID",
    "3 times a day": "TID",
    "3 times per day": "TID",
    "3 times daily": "TID",
    "3 per day": "TID",
    "three times a day": "TID",

    "qid": "QID",
    "4/day": "QID",
    "every 6 hours": "QID",
    "q6h": "QID",
    "four times a day": "QID",
    "4x daily": "QID",
    "4x/day": "QID",
    "4 times/day": "QID",
    "4x a day": "QID",
    "4x per day": "QID",
    "4 times a day": "QID",
    "4 times per day": "QID",
    "4 times daily": "QID",
    "4 per day": "QID",

    "5x daily": "5x daily",
    "5x/day": "5x daily",
    "5 times/day": "5x daily",
    "5x a day": "5x daily",
    "5x per day": "5x daily",
    "5 times a day": "5x daily",
    "5 times per day": "5x daily",
    "5 times daily": "5x daily",
    "5 per day": "5x daily",
    "five times a day": "5x daily",

    "6x daily": "6x daily",
    "6x/day": "6x daily",
    "6 times/day": "6x daily",
    "6x a day": "6x daily",
    "6x per day": "6x daily",
    "6 times a day": "6x daily",
    "6 times per day": "6x daily",
    "6 times daily": "6x daily",
    "6 per day": "6x daily",
    "six times a day": "6x daily",

    "8x daily": "8x daily",
    "8x/day": "8x daily",
    "8 times/day": "8x daily",
    "8x a day": "8x daily",
    "8x per day": "8x daily",
    "8 times a day": "8x daily",
    "8 times per day": "8x daily",
    "8 times daily": "8x daily",
    "8 per day": "8x daily",

    "4-6x daily": "4-6x daily",
    "4-6x/day" : "4-6x daily",

    "q1h": "hourly",
    "q hourly": "hourly",
    "every hour": "hourly",
    "q hour": "hourly",

    "q2h": "every 2 hours",
    "q2 hour": "every 2 hours",
    "every 2 hours": "every 2 hours",
    "every 2h": "every 2 hours",
    "every two hours": "every 2 hours",
    "q two hours": "every 2 hours",

    "q3h": "every 3 hours",
    "q3 hour": "every 3 hours",
    "every 3 hours": "every 3 hours",
    "every 3h": "every 3 hours",
    "every three hours": "every 3 hours",
    "q three hours": "every 3 hours",

    "q4h": "every 4 hours",
    "q4 hour": "every 4 hours",
    "every 4 hours": "every 4 hours",
    "every 4h": "every 4 hours",
    "every four hours": "every 4 hours",
    "q four hours": "every 4 hours",

    "weekly": "weekly",
    "once weekly": "weekly",
    "once a week": "weekly",
    "qw": "weekly",
    "every week": "weekly",

    "2x per week": "2x weekly",
    "2 per week": "2x weekly",
    "2 times per week": "2x weekly",
    "2x weekly" : "2x weekly",
    "2x/week" : "2x weekly",
    "2 times/week" : "2x weekly",
    "2x a week" : "2x weekly",
    "2x per week" : "2x weekly",
    "2 times per week" : "2x weekly",
    "2 times weekly" : "2x weekly",
    "2 per week" : "2x weekly",
    "twice weekly": "2x weekly",
    "twice a week": "2x weekly",

    "prn": "PRN",
    "as needed": "PRN",
    "when needed": "PRN",
    "as necessary": "PRN",

    "qod": "QOD",
    "every other day": "QOD",
}

LATERALITY_MAP = {
    "od": "OD",
    "right": "OD",
    "r": "OD",
    "os": "OS",
    "left": "OS",
    "l": "OS",
    "ou": "OU",
    "both": "OU",
    "both eyes": "OU",
    "bilateral": "OU",
}

NONE_TOKENS = {
    "none",
    "no",
    "no medications",
    "no meds",
    "no meds found",
    "no topical medications",
    "no changes",
    "no medication changes",
    "nothing",
    "n/a",
    "not applicable",
}

UNSPECIFIED_TOKEN = "unspecified"
LATERALITY_UNKNOWN_PLACEHOLDER = "(laterality unknown)"

