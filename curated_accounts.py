"""
curated_accounts.py — Static list of curated smart-money handles.

Extracted from the retired x_fetch.py (X/Twitter API integration retired
2026-06-22, API fully removed 2026-07-10). This is a PLAIN STATIC LIST — no
API calls, no credentials. Agent 3 uses it for its bearish-veto principal
list; preflight uses it for display. Nothing here touches the network.
"""

CURATED_ACCOUNTS = [
    # --- MACRO FLOW/SENTIMENT (institutional grade) ---
    "DeItaone",            # Institutional news wire
    "Fxhedgers",           # Macro/FX institutional feed
    "zaborsky",            # Macro strategist
    "GurufocusData",       # Fundamental data aggregator
    "PeterSchiff",         # Macro economist, hard assets
    "TruthGundlach",       # Jeffrey Gundlach, DoubleLine Capital
    "elerianm",            # Mohamed El-Erian, Allianz/PIMCO
    "SqueezeMetrics",      # DIX/GEX quant model
    "sentimentrader",      # Institutional sentiment data
    "DarkPoolChart",       # Dark pool flow analytics
    "VolSignals",          # Volatility structure analysis
    # --- MACRO_ANALYSTS (central bank, liquidity, regime) ---
    "MacroAlf",            # Alfonso Peccatiello, ex-ING $20B portfolio
    "FedGuy12",            # Joseph Wang, ex-NY Fed open market desk
    "biancoresearch",      # Jim Bianco, Bianco Research
    "TheMichaelEvery",     # Michael Every, Rabobank Global Strategist
    # --- SECTOR_SPECIALISTS ---
    "Josh_Young_1",        # Energy/oil specialist
    "brandon_munro",       # Uranium/nuclear sector
    "UraniumInsider",      # Uranium sector intelligence
    "PeterKolchinsky",     # Biotech/healthcare specialist
    "dylanpatel",          # Semiconductor/AI sector (SemiAnalysis)
    # --- QUANT_SYSTEMATIC (gamma, vol structure, quant models) ---
    "spotgamma",           # Options gamma exposure modeling
    "choffstein",          # Corey Hoffstein, Newfound Research
    "nope_its_lily",       # Lily Francus, options/vol quant
    # --- HEDGE_FUND_PRINCIPALS ---
    "boazweinstein",       # Boaz Weinstein, Saba Capital
    "CliffordAsness",      # Cliff Asness, AQR Capital
    "DylanLeClair_",       # Dylan LeClair, BTC/macro analyst
    "cngarabedian",        # Institutional fund manager
    "RayDalio",            # Ray Dalio, Bridgewater founder
    # --- CONTRARIAN_VOICES ---
    "WallStCynic",         # Contrarian macro voice
    "rampagingruss",       # Contrarian analyst
    "orrdavid",            # David Orr, contrarian macro
    # REMOVED per Jamie directive (May 19): benjamincowen, 0xReflection,
    # InTheAssembly, NoLimitGains, realDonaldTrump, TheGoldPrairie, great_martis
]
