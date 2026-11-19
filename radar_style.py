def signal_label(signal):
    value = str(signal).upper()
    if "CONFIRMED LONG" in value: return "🟢🟢 CONFIRMED LONG"
    if "EARLY LONG" in value: return "🟢 EARLY LONG"
    if "CONFIRMED SHORT" in value: return "🔴🔴 CONFIRMED SHORT"
    if "EARLY SHORT" in value: return "🔴 EARLY SHORT"
    if "PRE-LONG" in value: return "🟡 PRE-LONG"
    if "PRE-SHORT" in value: return "🟡 PRE-SHORT"
    if "WATCH LONG" in value: return "🟡 WATCH LONG"
    if "WATCH SHORT" in value: return "🟡 WATCH SHORT"
    if "LATE ENTRY" in value: return "⛔ LATE ENTRY"
    if "HOT ENTRY" in value: return "🔥 HOT ENTRY"
    if "CONTEXT CONFLICT" in value: return "⚠️ CONTEXT CONFLICT"
    if "NO TRADE" in value: return "⛔ NO TRADE"
    return "⚪ WAIT"


def grade_label(value):
    return {"A+": "🟢 A+", "A": "🟢 A", "B": "🟡 B", "C": "🟠 C", "-": "⚪ -"}.get(str(value), str(value))


def entry_label(value):
    value = str(value).upper()
    if "OPTIMAL" in value: return "🟢 OPTIMAL"
    if "AKZEPTABEL" in value: return "🟡 AKZEPTABEL"
    if "SPÄT" in value: return "🔴 SPÄT"
    return value


def regime_label(value):
    value = str(value).upper()
    return "🟢 LONG" if value == "LONG" else "🔴 SHORT" if value == "SHORT" else "⚪ NEUTRAL"


def prepare_radar(df):
    result = df.copy()
    result["Signal"] = result["Signal"].map(signal_label)
    result["Grade"] = result["Grade"].map(grade_label)
    result["Entry Status"] = result["Entry Status"].map(entry_label)
    for column in ("60m Regime", "15m Bias"):
        result[column] = result[column].map(regime_label)
    return result
