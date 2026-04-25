"""
BC Federal Electoral District name-to-abbreviation mapping.
Used by scripts that process BC QSO Party logs and generate maps.

Keys are the official English district names from the 2023 Representation Order
(as found in Elections Canada shapefiles). Values are the 3-letter abbreviations
used in the BC QSO Party exchange.
"""

# Maps official ED_NAMEE (from Elections Canada 2023 shapefile) -> BCQP 3-letter code
BC_DISTRICT_CODES = {
    "Abbotsford\u2014South Langley":                    "ASL",
    "Burnaby Central":                                   "BUC",
    "Burnaby North\u2014Seymour":                        "BNS",
    "Cariboo\u2014Prince George":                        "CPG",
    "Chilliwack\u2014Hope":                              "CHP",
    "Cloverdale\u2014Langley City":                      "CLC",
    "Columbia\u2014Kootenay\u2014Southern Rockies":      "CKS",
    "Coquitlam\u2014Port Coquitlam":                     "CPC",
    "Courtenay\u2014Alberni":                            "COA",
    "Cowichan\u2014Malahat\u2014Langford":               "CML",
    "Delta":                                             "DEL",
    "Esquimalt\u2014Saanich\u2014Sooke":                 "ESQ",
    "Fleetwood\u2014Port Kells":                         "FPK",
    "Kamloops\u2014Shuswap\u2014Central Rockies":        "KSC",
    "Kamloops\u2014Thompson\u2014Nicola":                "KTN",
    "Kelowna":                                           "KEL",
    "Langley Township\u2014Fraser Heights":              "LTF",
    "Mission\u2014Matsqui\u2014Abbotsford":              "MMA",
    "Nanaimo\u2014Ladysmith":                            "NAL",
    "New Westminster\u2014Burnaby\u2014Maillardville":   "NBM",
    "North Island\u2014Powell River":                    "NPR",
    "North Vancouver\u2014Capilano":                     "NVC",
    "Okanagan Lake West\u2014South Kelowna":             "OSK",
    "Pitt Meadows\u2014Maple Ridge":                     "PMM",
    "Port Moody\u2014Coquitlam":                         "PMC",
    "Prince George\u2014Peace River\u2014Northern Rockies": "PPN",
    "Richmond Centre\u2014Marpole":                      "RCM",
    "Richmond East\u2014Steveston":                      "RES",
    "Saanich\u2014Gulf Islands":                         "SGI",
    "Similkameen\u2014South Okanagan\u2014West Kootenay": "SSW",
    "Skeena\u2014Bulkley Valley":                        "SBV",
    "South Surrey\u2014White Rock":                      "SWR",
    "Surrey Centre":                                     "SUC",
    "Surrey Newton":                                     "SUN",
    "Vancouver Centre":                                  "VAC",
    "Vancouver East":                                    "VAE",
    "Vancouver Fraserview\u2014South Burnaby":           "VSB",
    "Vancouver Granville":                               "VAG",
    "Vancouver Kingsway":                                "VAK",
    "Vancouver Quadra":                                  "VAQ",
    "Vernon\u2014Lake Country\u2014Monashee":            "VLM",
    "Victoria":                                          "VIC",
    "West Vancouver\u2014Sunshine Coast\u2014Sea to Sky Country": "WVS",
}

# Reverse mapping: abbreviation -> full name
BC_CODE_TO_NAME = {v: k for k, v in BC_DISTRICT_CODES.items()}

# All valid 3-letter codes
BC_DISTRICT_ABBREVS = set(BC_DISTRICT_CODES.values())
