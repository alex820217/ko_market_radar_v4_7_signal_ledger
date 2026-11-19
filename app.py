from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from market_universe import MARKET_GROUPS,build_universe,all_assets
from scanner_engine import scan_asset,market_open
from radar_style import prepare_radar,signal_label
from storage import save_scan,find_signal,create_trade,update_trade,close_trade,delete_trade,correct_trade,load,learning_frame,journal_frame,backup,restore
from position_manager import evaluate
st.set_page_config(page_title='KO Market Radar V4.7',page_icon='📡',layout='wide')
st.title('📡 KO Market Radar V4.7.2 · Signal Ledger')
st.caption('Signal wird mit Uhrzeit eingefroren · Kaufzeit verknüpft den richtigen Snapshot · nur verifizierte Snapshots lernen')
ASSETS=all_assets();LABELS=[f'{n} ({t})' for n,t,g in ASSETS];BY={f'{n} ({t})':(n,t) for n,t,g in ASSETS}
def lab(ticker):return next((key for key,val in BY.items() if val[1]==ticker),LABELS[0])
def eur(x):return f'{x:+.2f} €'
def balance():
    rows=load();realized=open_pnl=0
    for row in rows:
        mark=row['certificate_exit'] if row['status']=='CLOSED' else row['last_price'];pnl=(mark-row['certificate_entry'])*row['quantity'];realized+=pnl if row['status']=='CLOSED' else 0;open_pnl+=pnl if row['status']=='OPEN' else 0
    c=st.columns(4);c[0].metric('Gesamt P/L',eur(realized+open_pnl));c[1].metric('Realisiert',eur(realized));c[2].metric('Offen',eur(open_pnl));c[3].metric('Trades',len(rows))
balance();tabs=st.tabs(['🔥 Radar & Kauf','💼 Open Position Manager','📓 Journal & Lernen','💾 Backup'])
scan=pd.DataFrame()
with tabs[0]:
    groups=st.sidebar.multiselect('Marktgruppen',list(MARKET_GROUPS),default=['Deutschland','US Tech','Indizes']);only_open=st.sidebar.checkbox('Geschlossene Märkte überspringen',True);maximum=st.sidebar.slider('Max. Assets',10,50,30)
    items=build_universe(groups)[:maximum];items=[x for x in items if not(only_open and not market_open(x['ticker']))];rows=[];progress=st.progress(0)
    for index,meta in enumerate(items,1):
        try:rows.append(scan_asset(meta))
        except Exception:pass
        progress.progress(index/max(1,len(items)))
    progress.empty()
    if rows:
        scan=pd.DataFrame(rows).sort_values(['Score','ADX'],ascending=False);save_scan(scan)
        columns=['Asset','Signal','Grade','Score','60m Regime','15m Bias','5m Setup','3m Trigger','Entry Status','Setup-Hinweis'];st.dataframe(prepare_radar(scan[columns]),use_container_width=True,hide_index=True)
        chosen=st.selectbox('Radar-Signal auswählen',scan.Asset.tolist());row=scan[scan.Asset==chosen].iloc[0];st.subheader(f'{row.Asset} · {signal_label(row.Signal)}')
        base_label=st.selectbox('Basiswert des gekauften Produkts',LABELS,index=LABELS.index(lab(row.Ticker)));asset,ticker=BY[base_label]
        c1,c2=st.columns(2);day=c1.date_input('Kaufdatum',datetime.now().date());clock=c2.time_input('Kaufzeit',datetime.now().time().replace(second=0,microsecond=0));trade_time=datetime.combine(day,clock).astimezone().astimezone(timezone.utc).isoformat(timespec='seconds')
        direction=st.selectbox('Richtung',['LONG','SHORT'],index=0 if 'LONG' in row.Signal else 1);match=find_signal(ticker,trade_time,direction,max_minutes=20)
        if match:
            snap=match['snapshot'];st.success(f"Passendes Signal gefunden: {snap.get('Asset')} · {snap.get('Signal')} · Grade {snap.get('Grade')} · Score {snap.get('Score')} · {match['age_minutes']:.1f} Min. vor Kauf")
            verified=st.checkbox('Ja, genau dieses Signal war mein Kaufsignal')
        else:
            st.error('Kein passendes Signal bis 20 Minuten vor Kaufzeit gefunden. Dieser Trade kann nur unverifiziert lernen.');verified=False
        with st.form('trade'):
            a,b,c,d=st.columns(4);wkn=a.text_input('WKN').upper();entry=b.number_input('Kaufpreis',.0001,value=1.22,format='%.4f');quantity=c.number_input('Stückzahl',1,value=1639);stop=d.number_input('Stop',.0001,value=1.1495,format='%.4f');notes=st.text_input('Notiz');save=st.form_submit_button('Trade speichern',type='primary')
        if save:
            source='SYSTEM_SIGNAL' if match else 'MANUAL_OR_HISTORICAL';create_trade(wkn,asset,ticker,direction,trade_time,entry,stop,quantity,match,verified,source,notes);st.success('Trade gespeichert. Nur bestätigte Signalverknüpfungen fließen in den Lerndatensatz.');st.rerun()
with tabs[1]:
    for trade in load('OPEN'):
        with st.container(border=True):
            try:market=scan_asset({'name':trade['asset'],'ticker':trade['ticker']})
            except Exception:market=None
            advice=evaluate(trade,market);current=trade['last_price'];pnl=(current-trade['certificate_entry'])*trade['quantity'];st.subheader(f"{trade['wkn']} · {trade['asset']} · {trade['direction']}");c=st.columns(5);c[0].metric('Aktion',advice.action);c[1].metric('Score',f'{advice.score}/100');c[2].metric('Kurs',f'{current:.4f} €');c[3].metric('P/L',eur(pnl));c[4].metric('Empf. Stop',f'{advice.stop:.4f} €')
            with st.expander('✏️ Basiswert korrigieren'):
                choice=st.selectbox('Basiswert',LABELS,index=LABELS.index(lab(trade['ticker'])),key='asset'+trade['id']);name,ticker=BY[choice];direction=st.selectbox('Richtung',['LONG','SHORT'],index=0 if trade['direction']=='LONG' else 1,key='dir'+trade['id']);wkn=st.text_input('WKN',trade['wkn'],key='wkn'+trade['id']);
                if st.button('Korrektur speichern',key='meta'+trade['id']):correct_trade(trade['id'],name,ticker,direction,wkn);st.rerun()
            with st.form('update'+trade['id']):
                a,b=st.columns(2);price=a.number_input('Aktueller Geldkurs',.0001,value=float(current),format='%.4f');stop=b.number_input('Aktueller Stop',.0001,value=float(trade['certificate_stop']),format='%.4f');update=st.form_submit_button('Aktualisieren')
            if update:update_trade(trade['id'],price,stop);st.rerun()
            with st.expander('Technische Gründe'):
                for reason in advice.reasons:st.write('• '+reason)
            with st.form('close'+trade['id']):
                price=st.number_input('Verkaufskurs',.0001,value=float(current),format='%.4f');reason=st.selectbox('Exitgrund',['Stop','Trailing-Stop','Gewinnziel','Trendbruch','Manuell','Handelsschluss']);close=st.form_submit_button('Trade schließen')
            if close:close_trade(trade['id'],price,reason);st.rerun()
with tabs[2]:
    journal=journal_frame();learning=learning_frame();st.subheader('Gesamtes Journal');st.dataframe(journal,use_container_width=True,hide_index=True);st.subheader('Verifizierter Lerndatensatz');st.dataframe(learning,use_container_width=True,hide_index=True)
    st.caption(f'{len(learning)} verifizierte Trades von {len(journal)} Journal-Trades fließen in die Signalstatistik ein.')
    if not journal.empty:
        options={f"{r['wkn']} · {r['asset']} · {r['status']} · {r['id'][:8]}":r['id'] for _,r in journal.iterrows()};label=st.selectbox('Falschen Trade löschen',list(options));sure=st.checkbox('Dauerhaftes Löschen bestätigen');
        if st.button('🗑️ Endgültig löschen',disabled=not sure):delete_trade(options[label]);st.rerun()
with tabs[3]:
    st.warning('SQLite auf Streamlit Cloud ist nicht garantiert dauerhaft. Backup regelmäßig herunterladen.');st.download_button('SQLite-Backup',backup(),'trade_journal.sqlite3','application/octet-stream');upload=st.file_uploader('Backup wiederherstellen',type=['sqlite3','db']);
    if upload and st.button('Backup einspielen'):restore(upload.read());st.rerun()
st.caption('Technische Entscheidungshilfe. Keine automatische Order und keine Gewinngarantie.')
