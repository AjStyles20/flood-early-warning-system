#!/usr/bin/env python3
"""FloodWatch Experiment 001: B3 trend baseline vs lightweight Random Forest.

Supply the downloaded GRDC 1834101 daily discharge file with --data.
Raw GRDC observations are intentionally not bundled in the repository.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix

TRAIN=("2004-01-01","2014-12-31")
VALID=("2015-01-01","2019-12-31")
TEST=("2020-01-01","2025-12-31")
QUANTILES=(0.90,0.95,0.975)
HORIZONS=(1,3,5,7)
TREND_WINDOWS=(1,2,3,5,7,14)

def load_grdc(path):
    df=pd.read_csv(path,sep=";",comment="#",skipinitialspace=True,encoding="latin1")
    df.columns=[c.strip() for c in df.columns]
    if "YYYY-MM-DD" not in df or "Value" not in df:
        raise ValueError("Expected GRDC daily columns YYYY-MM-DD and Value")
    df["date"]=pd.to_datetime(df["YYYY-MM-DD"])
    df["q"]=pd.to_numeric(df["Value"],errors="coerce").replace(-999,np.nan)
    s=df.set_index("date")["q"].sort_index()
    if s.index.duplicated().any(): raise ValueError("Duplicate dates found")
    return s

def features(s):
    x=pd.DataFrame(index=s.index); x["q0"]=s
    for lag in (1,2,3,5,7,14): x[f"lag{lag}"]=s.shift(lag)
    x["d1"]=s-s.shift(1); x["d3"]=(s-s.shift(3))/3; x["d7"]=(s-s.shift(7))/7
    for w in (3,7,14):
        r=s.rolling(w)
        x[f"mean{w}"]=r.mean(); x[f"std{w}"]=r.std()
        x[f"min{w}"]=r.min(); x[f"max{w}"]=r.max()
    return x

def labels(s,T,H):
    a=s.to_numpy(); y=np.full(len(a),np.nan)
    for i in range(len(a)-H):
        if not np.isfinite(a[i]) or a[i]>=T: continue
        fut=a[i+1:i+H+1]
        if np.all(np.isfinite(fut)): y[i]=float(np.max(fut)>=T)
    return pd.Series(y,index=s.index)

def metric(y,p):
    tn,fp,fn,tp=confusion_matrix(np.asarray(y,int),np.asarray(p,int),labels=[0,1]).ravel()
    return {"tp":int(tp),"fp":int(fp),"fn":int(fn),"tn":int(tn),
      "POD":tp/(tp+fn) if tp+fn else None,
      "FAR":fp/(tp+fp) if tp+fp else 0.0,
      "CSI":tp/(tp+fp+fn) if tp+fp+fn else None,
      "F1":2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}

def b3(s,T,H,w):
    slope=(s-s.shift(w))/w
    return (s+H*slope>=T).astype(int)

def events(s,T,H,pred):
    ex=(s>=T)&s.notna(); starts=list(s.index[ex&~ex.shift(1,fill_value=False)])
    usable=det=0; leads=[]
    for onset in starts:
        prior=pred.loc[onset-pd.Timedelta(days=H):onset-pd.Timedelta(days=1)].dropna()
        if prior.empty: continue
        usable+=1; hits=prior[prior.astype(int)==1]
        if not hits.empty:
            det+=1; leads.append((onset-hits.index[0]).days)
    return {"events_total":len(starts),"events_usable":usable,"events_detected":det,
      "event_recall":det/usable if usable else None,
      "lead_days_mean":float(np.mean(leads)) if leads else None}

def run(data):
    split={"train":data.loc[TRAIN[0]:TRAIN[1]],"validation":data.loc[VALID[0]:VALID[1]],"test":data.loc[TEST[0]:TEST[1]]}
    Xall=features(data); out=[]
    for q in QUANTILES:
        T=float(split["train"].dropna().quantile(q))
        for H in HORIZONS:
            yall=labels(data,T,H); prepared={}
            for name,s in split.items():
                X=Xall.loc[s.index]; y=yall.loc[s.index]
                mask=X.notna().all(axis=1)&y.notna()
                prepared[name]=(X.loc[mask],y.loc[mask].astype(int))
            choices=[]
            for w in TREND_WINDOWS:
                pv=b3(data,T,H,w).loc[prepared["validation"][0].index]
                m=metric(prepared["validation"][1],pv)
                choices.append((m["CSI"],-m["FAR"],w))
            _,_,bw=max(choices)
            pbt=b3(data,T,H,bw).loc[prepared["test"][0].index]; mb=metric(prepared["test"][1],pbt)
            rf=RandomForestClassifier(n_estimators=500,max_depth=6,min_samples_leaf=5,class_weight="balanced_subsample",random_state=42,n_jobs=-1)
            rf.fit(*prepared["train"])
            vp=rf.predict_proba(prepared["validation"][0])[:,1]; cuts=[]
            for c in np.arange(.05,.96,.05):
                m=metric(prepared["validation"][1],(vp>=c).astype(int))
                cuts.append((m["CSI"],-m["FAR"],-abs(c-.5),c))
            *_,cut=max(cuts)
            rp=(rf.predict_proba(prepared["test"][0])[:,1]>=cut).astype(int); mr=metric(prepared["test"][1],rp)
            bs=pd.Series(np.nan,index=split["test"].index); bs.loc[prepared["test"][0].index]=pbt.to_numpy()
            rs=pd.Series(np.nan,index=split["test"].index); rs.loc[prepared["test"][0].index]=rp
            out.append({"threshold_quantile":q,"threshold_m3s":T,"horizon_days":H,
              "b3_trend_window_days":bw,"b3":mb,"b3_event":events(split["test"],T,H,bs),
              "rf_probability_cutoff":float(cut),"rf":mr,"rf_event":events(split["test"],T,H,rs)})
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data",required=True,type=Path); ap.add_argument("--out",type=Path,default=Path("experiment_001_results.json"))
    a=ap.parse_args(); a.out.write_text(json.dumps(run(load_grdc(a.data)),indent=2),encoding="utf-8"); print(f"Wrote {a.out}")
if __name__=="__main__": main()
