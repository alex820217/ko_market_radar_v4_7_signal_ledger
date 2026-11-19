import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
DB = Path(__file__).with_name("trade_journal.sqlite3")

def connect():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    # Keep the legacy trade schema compatible with V4.3/V4.4 backups.
    c.execute("""CREATE TABLE IF NOT EXISTS trades(
      id TEXT PRIMARY KEY,status TEXT NOT NULL,wkn TEXT,asset TEXT,ticker TEXT,direction TEXT,
      entry_time TEXT,exit_time TEXT,certificate_entry REAL,certificate_stop REAL,certificate_exit REAL,
      quantity REAL,investment REAL,highest_price REAL,lowest_price REAL,exit_reason TEXT,
      signal_snapshot TEXT,product_snapshot TEXT,notes TEXT,last_price REAL)""")
    existing={r[1] for r in c.execute("PRAGMA table_info(trades)")}
    migrations={
      'last_price':'REAL','signal_id':'TEXT','snapshot_verified':'INTEGER DEFAULT 0',
      'trade_source':"TEXT DEFAULT 'HISTORICAL'"
    }
    for name,sqltype in migrations.items():
        if name not in existing:c.execute(f"ALTER TABLE trades ADD COLUMN {name} {sqltype}")
    c.execute("""CREATE TABLE IF NOT EXISTS signals(
      signal_id TEXT PRIMARY KEY,recorded_at TEXT,asset TEXT,ticker TEXT,direction TEXT,
      signal TEXT,grade TEXT,score REAL,snapshot TEXT)""")
    c.execute('CREATE INDEX IF NOT EXISTS idx_signals_ticker_time ON signals(ticker,recorded_at)')
    c.commit();return c

def now_utc():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def safe(value):
    if hasattr(value,'item'):
        try:return value.item()
        except:pass
    if pd.isna(value):return None
    return value

def save_signal(row, recorded_at=None):
    snap={str(k):safe(v) for k,v in dict(row).items()};signal=str(snap.get('Signal',''));direction='LONG' if 'LONG' in signal else 'SHORT' if 'SHORT' in signal else None;sid=str(uuid.uuid4());c=connect()
    c.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)',(sid,recorded_at or now_utc(),str(snap.get('Asset','')),str(snap.get('Ticker','')),direction,signal,str(snap.get('Grade','-')),float(snap.get('Score') or 0),json.dumps(snap,ensure_ascii=False,default=str)));c.commit();c.close();return sid

def save_scan(frame):
    timestamp=now_utc();ids=[]
    for _,row in frame.iterrows():
        if any(k in str(row.get('Signal','')) for k in ('WATCH','PRE','EARLY','CONFIRMED')):ids.append(save_signal(row.to_dict(),timestamp))
    return ids

def find_signal(ticker,trade_time,direction=None,max_minutes=20):
    c=connect();params=[ticker,trade_time];query='SELECT * FROM signals WHERE ticker=? AND recorded_at<=?'
    if direction:query+=' AND direction=?';params.append(direction)
    query+=' ORDER BY recorded_at DESC LIMIT 1';row=c.execute(query,params).fetchone();c.close()
    if not row:return None
    d=dict(row);age=(datetime.fromisoformat(trade_time)-datetime.fromisoformat(d['recorded_at'])).total_seconds()/60
    if age<0 or age>max_minutes:return None
    d['age_minutes']=age;d['snapshot']=json.loads(d['snapshot']);return d

def create_trade(wkn,asset,ticker,direction,trade_time,entry,stop,quantity,signal=None,verified=False,source='SYSTEM_SIGNAL',notes=''):
    tid=str(uuid.uuid4());entry=float(entry);quantity=float(quantity);signal_id=signal.get('signal_id') if signal else None
    c=connect()
    cols={r[1] for r in c.execute("PRAGMA table_info(trades)")}
    values={
      'id':tid,'status':'OPEN','wkn':wkn.upper(),'asset':asset,'ticker':ticker,'direction':direction,
      'entry_time':trade_time,'exit_time':None,'certificate_entry':entry,'certificate_stop':float(stop),
      'certificate_exit':None,'quantity':quantity,'investment':entry*quantity,'highest_price':entry,
      'lowest_price':entry,'exit_reason':None,'notes':notes,'last_price':entry,'signal_id':signal_id,
      'snapshot_verified':1 if verified else 0,'trade_source':source
    }
    # Legacy columns are populated too, so old journal views/backups remain usable.
    if 'signal_snapshot' in cols:
        values['signal_snapshot']=json.dumps(signal.get('snapshot',{}) if signal else {},ensure_ascii=False,default=str)
    if 'product_snapshot' in cols:values['product_snapshot']='{}'
    names=[k for k in values if k in cols];placeholders=','.join('?' for _ in names)
    c.execute(f"INSERT INTO trades ({','.join(names)}) VALUES ({placeholders})",[values[k] for k in names])
    c.commit();c.close();return tid

def update_trade(tid,current,stop):
    c=connect();row=c.execute('SELECT * FROM trades WHERE id=?',(tid,)).fetchone();current=float(current)
    if row:c.execute('UPDATE trades SET highest_price=?,lowest_price=?,last_price=?,certificate_stop=? WHERE id=?',(max(row['highest_price'],current),min(row['lowest_price'],current),current,float(stop),tid));c.commit();c.close()
def close_trade(tid,price,reason):
    c=connect();price=float(price);c.execute("UPDATE trades SET status='CLOSED',certificate_exit=?,last_price=?,exit_reason=?,exit_time=? WHERE id=?",(price,price,reason,now_utc(),tid));c.commit();c.close()
def delete_trade(tid):
    c=connect();c.execute('DELETE FROM trades WHERE id=?',(tid,));c.commit();c.close()
def correct_trade(tid,asset,ticker,direction,wkn):
    c=connect();c.execute('UPDATE trades SET asset=?,ticker=?,direction=?,wkn=?,snapshot_verified=0 WHERE id=?',(asset,ticker,direction,wkn.upper(),tid));c.commit();c.close()
def load(status=None):
    c=connect();q='SELECT * FROM trades'+(' WHERE status=?' if status else '')+' ORDER BY entry_time DESC';rows=c.execute(q,(status,) if status else ()).fetchall();c.close();return [dict(r) for r in rows]
def signal_for_trade(row):
    if not row.get('signal_id'):return None
    c=connect();sig=c.execute('SELECT * FROM signals WHERE signal_id=?',(row['signal_id'],)).fetchone();c.close()
    if not sig:return None
    result=dict(sig);result['snapshot']=json.loads(result['snapshot']);return result

def learning_frame():
    rows=[]
    for trade in load():
        sig=signal_for_trade(trade)
        if not sig or not trade['snapshot_verified']:continue
        entry=trade['certificate_entry'];exit_=trade['certificate_exit'];risk=entry-trade['certificate_stop'];snap=sig['snapshot'];row={**trade,**{f'signal_{k}':v for k,v in snap.items()}}
        row['pnl_eur']=(exit_-entry)*trade['quantity'] if exit_ is not None else None;row['pnl_pct']=(exit_/entry-1)*100 if exit_ is not None else None;row['r_multiple']=(exit_-entry)/risk if exit_ is not None and risk>0 else None;row['mfe_pct']=(trade['highest_price']/entry-1)*100;row['mae_pct']=(trade['lowest_price']/entry-1)*100;rows.append(row)
    return pd.DataFrame(rows)
def journal_frame():
    rows=[]
    for trade in load():
        entry=trade['certificate_entry'];mark=trade['certificate_exit'] if trade['status']=='CLOSED' else trade['last_price'];row=dict(trade);row['pnl_eur']=(mark-entry)*trade['quantity'];row['pnl_pct']=(mark/entry-1)*100;rows.append(row)
    return pd.DataFrame(rows)
def backup():return DB.read_bytes() if DB.exists() else b''
def restore(data):DB.write_bytes(data)
