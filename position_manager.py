from dataclasses import dataclass
@dataclass
class Advice: action:str; score:int; stop:float; reasons:list

def number(value):
    try:return int(str(value).split('/')[0])
    except:return 0
def trailing(entry,performance):
    if performance<5:return None
    return entry*(1+max(0,(int(performance//5)-1)*5)/100)
def evaluate(trade,market):
    entry=float(trade['certificate_entry']);current=float(trade['last_price']);stop=float(trade['certificate_stop']);quantity=float(trade['quantity']);performance=(current/entry-1)*100
    if current<=stop:return Advice('⛔ STOP ERREICHT',0,stop,[f'Geldkurs {current:.4f} <= Stop {stop:.4f}'])
    proposed=trailing(entry,performance)
    if not market:return Advice('⚪ MANUELL PRÜFEN',50,proposed or stop,['Keine aktuelle Basiswertanalyse verfügbar'])
    direction=trade['direction'];score=0;reasons=[]
    for key,points in [('60m Regime',25),('15m Bias',25)]:
        value=market.get(key);score+=points if value==direction else 12 if value=='NEUTRAL' else 0;reasons.append(f'{key}: {value}')
    setup=number(market.get('5m Setup'));trigger=number(market.get('3m Trigger'));adx=float(market.get('ADX') or 0);score+=min(20,setup*5)+min(10,trigger*3)+(10 if adx>=20 else 5 if adx>=15 else 0)+(10 if performance>=0 else 5 if performance>-3 else 0)
    conflicts=sum([market.get('60m Regime') not in {direction,'NEUTRAL'},market.get('15m Bias')!=direction,setup<2,adx<15])
    action='🔴 EXIT PRÜFEN' if conflicts>=3 or score<50 else '🟠 GEWINN ABSICHERN' if performance>=5 and conflicts>=2 else '🟡 STOP NACHZIEHEN' if proposed and proposed>stop else '🟢 HALTEN' if score>=80 else '🟡 BEOBACHTEN' if score>=65 else '🟠 GEWINN ABSICHERN'
    reasons += [f'5m {market.get("5m Setup")}',f'3m {market.get("3m Trigger")}',f'ADX {adx:.1f}',f'Zertifikat {performance:+.2f}%']
    return Advice(action,max(0,min(100,score)),proposed or stop,reasons)
