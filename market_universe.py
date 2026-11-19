MARKET_GROUPS = {
    "Deutschland": {
        "DAX": "^GDAXI", "SAP": "SAP.DE", "Siemens": "SIE.DE", "Allianz": "ALV.DE",
        "Deutsche Telekom": "DTE.DE", "Airbus": "AIR.DE", "Rheinmetall": "RHM.DE",
        "Mercedes-Benz": "MBG.DE", "BMW": "BMW.DE", "BASF": "BAS.DE",
        "Infineon": "IFX.DE", "Deutsche Bank": "DBK.DE", "Commerzbank": "CBK.DE",
        "Adidas": "ADS.DE", "Vonovia": "VNA.DE", "DHL Group": "DHL.DE",
    },
    "US Tech": {
        "Microsoft": "MSFT", "Apple": "AAPL", "NVIDIA": "NVDA", "Amazon": "AMZN",
        "Meta": "META", "Alphabet": "GOOGL", "Tesla": "TSLA", "AMD": "AMD",
        "Broadcom": "AVGO", "Netflix": "NFLX", "Palantir": "PLTR", "Micron": "MU",
    },
    "Indizes": {
        "Nasdaq 100": "^NDX", "S&P 500": "^GSPC", "Dow Jones": "^DJI",
        "Euro Stoxx 50": "^STOXX50E", "Russell 2000": "^RUT",
    },
    "Metalle": {"Gold": "GC=F", "Silber": "SI=F", "Kupfer": "HG=F", "Platin": "PL=F"},
    "Energie": {"WTI Öl": "CL=F", "Brent Öl": "BZ=F", "Natural Gas": "NG=F"},
}


def build_universe(groups):
    rows, seen = [], set()
    for group in groups:
        for name, ticker in MARKET_GROUPS[group].items():
            if ticker not in seen:
                rows.append({"group": group, "name": name, "ticker": ticker})
                seen.add(ticker)
    return rows


def all_assets():
    return sorted(
        [(name, ticker, group) for group, assets in MARKET_GROUPS.items() for name, ticker in assets.items()],
        key=lambda item: item[0].casefold(),
    )
