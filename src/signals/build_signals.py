
"""Step 5 熱修補（denoise & zscore & UTC）：
- 修掉 pandas KeyError: 'ticker'：不再使用 groupby.apply(include_groups=False)，改以 transform 實作去噪；不會丟失分組鍵。
- 修正 zscore_30 計算：改為 (mean_score - rolling_mean) / rolling_std。
- 移除 utcnow() 警告：改用 timezone-aware `datetime.datetime.now(datetime.timezone.utc).date()`。
- 其他功能不變：加權聚合 / 新鮮度衰減 / 驚奇度 / NaN 清洗 / GETUTCDATE() / 分批查詢寫入 / CPU-only / 自動補欄位與建索引（若你用的是 ensure-tables2 版）。
"""
import argparse, json, time, math, datetime, yaml
from typing import List, Dict
import pandas as pd
from sqlalchemy import create_engine, text, bindparam
from src.config import DB_URL

# ----------------------------- helpers -----------------------------
def _now_utc_date():
    # timezone-aware，避免 DeprecationWarning
    return datetime.datetime.now(datetime.timezone.utc).date()

def _freshness_weight(published_date, tau_days: float) -> float:
    try:
        if published_date is None:
            return 1.0
        if isinstance(published_date, datetime.datetime):
            d = published_date.date()
        else:
            d = published_date
        dt = max((_now_utc_date() - d).days, 0)
        return math.exp(-dt / max(tau_days, 1e-6))
    except Exception:
        return 1.0

def _winsorize(s: pd.Series, low: float, high: float) -> pd.Series:
    if s.empty:
        return s
    lo = s.quantile(low); hi = s.quantile(high)
    return s.clip(lower=lo, upper=hi)

def _median_filter(s: pd.Series, window: int) -> pd.Series:
    if window <= 1 or len(s) == 0: return s
    return s.rolling(window, min_periods=1, center=True).median()

def _san(x, policy:str):
    if x is None: return None if policy=='null' else 0.0
    try:
        if pd.isna(x) or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
            return None if policy=='null' else 0.0
    except Exception:
        pass
    try:
        return float(x)
    except Exception:
        return None if policy=='null' else 0.0

def _load_authority(path:str):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            y = yaml.safe_load(f) or {}
        default = float(y.get('default', 1.0))
        table = {str(k): float(v) for k, v in (y.get('sources') or {}).items()}
        return default, table
    except Exception:
        return 1.0, {}

# ----------------------------- DB schema & fetch（與你現用版本一致） -----------------------------
def ensure_tables(engine):
    # 若你的環境已用 ensure-tables2 版，可保留原狀；此簡化版僅保證欄位存在
    with engine.begin() as conn:
        for tbl in ['signals_entity_daily','signals_industry_daily','signals_market_daily']:
            conn.execute(text(f"""
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = '{tbl}')
BEGIN
    CREATE TABLE {tbl} (
        id INT IDENTITY(1,1) PRIMARY KEY,
        { 'ticker NVARCHAR(32),' if 'entity' in tbl else '' }
        { 'industry NVARCHAR(64),' if 'industry' in tbl else '' }
        ds DATETIME NOT NULL,
        n_docs INT NULL,
        mean_score FLOAT NULL,
        ewma_20 FLOAT NULL,
        zscore_30 FLOAT NULL,
        cum30 FLOAT NULL
    );
END
"""))
            # 加欄位（若缺）
            for col in ['weighted_mean','surprise_src7']:
                conn.execute(text(f"""
IF COL_LENGTH('{tbl}', '{col}') IS NULL
BEGIN
    ALTER TABLE {tbl} ADD {col} FLOAT NULL;
END
"""))

def _fetch_docs(engine, days:int, limit:int):
    with engine.begin() as conn:
        rows = conn.execute(text('''
            SELECT TOP (:limit) d.news_id, CAST(d.created_at AS DATE) as ds, d.doc_score
            FROM news_doc_sentiment d
            WHERE d.created_at >= DATEADD(day, -:days, GETUTCDATE())
            ORDER BY d.news_id DESC
        '''), {'limit': limit, 'days': days}).fetchall()
    return rows

def _fetch_entities_for_ids(engine, ids: List[int], chunk_size=800, throttle_ms=0):
    if not ids: return []
    ids = [int(x) for x in ids]
    out = []
    with engine.begin() as conn:
        stmt = text("""
            SELECT n.news_id, n.matched_json
            FROM news_entity n
            WHERE n.news_id IN :ids
        """).bindparams(bindparam('ids', expanding=True))
        for i in range(0, len(ids), chunk_size):
            part = ids[i:i+chunk_size]
            out.extend(conn.execute(stmt, {'ids': part}).fetchall())
            if throttle_ms>0: time.sleep(throttle_ms/1000.0)
    return out

def _fetch_meta_for_ids(engine, ids: List[int], chunk_size=800, throttle_ms=0):
    out = []
    if not ids: return out
    tables = ['news_raw','raw_news']
    with engine.begin() as conn:
        for t in tables:
            try:
                conn.execute(text(f"SELECT TOP 1 1 FROM {t}"))
                stmt = text(f"""
                    SELECT r.news_id, r.source, CAST(r.published_at AS DATE) as pub_date
                    FROM {t} r WHERE r.news_id IN :ids
                """).bindparams(bindparam('ids', expanding=True))
                for i in range(0, len(ids), chunk_size):
                    part = ids[i:i+chunk_size]
                    out.extend(conn.execute(stmt, {'ids': part}).fetchall())
                    if throttle_ms>0: time.sleep(throttle_ms/1000.0)
                return out
            except Exception:
                continue
    return out

# ----------------------------- core calc -----------------------------
def _apply_weights(df_join: pd.DataFrame, auth_default:float, auth_table:Dict[str,float], tau_days:float) -> pd.Series:
    def auth(s):
        return auth_table.get(str(s), auth_default) if s is not None else auth_default
    w_auth = df_join['source'].map(lambda s: auth(s))
    w_fresh = df_join['pub_date'].map(lambda d: _freshness_weight(d, tau_days))
    return w_auth * w_fresh

def _denoise_inplace(df: pd.DataFrame, key: str, wl:float, wh:float, med:int):
    # 以 transform 實作：不會丟失分組鍵，也不會觸發 FutureWarning
    wins = df.groupby(key)['mean_score'].transform(lambda s: _winsorize(s, wl, wh))
    medf = wins.groupby(df[key]).transform(lambda s: _median_filter(s, med))
    df['mean_score'] = medf
    return df

def _calc_rollings(df: pd.DataFrame, key: str) -> pd.DataFrame:
    df = df.sort_values([key,'ds']).copy()
    g = df.groupby(key)['mean_score']
    roll_mean = g.transform(lambda s: s.rolling(30, min_periods=5).mean())
    roll_std  = g.transform(lambda s: s.rolling(30, min_periods=5).std().replace(0, pd.NA))
    df['ewma_20']   = g.transform(lambda s: s.ewm(span=20, adjust=False).mean())
    df['zscore_30'] = (df['mean_score'] - roll_mean) / roll_std
    df['cum30']     = g.transform(lambda s: s.rolling(30, min_periods=1).sum())
    return df

def _calc_surprise(df_daily: pd.DataFrame, key_cols: List[str]) -> pd.DataFrame:
    if 'source' not in df_daily.columns:
        df_daily = df_daily.assign(source='NA')
    df_daily = df_daily.sort_values(key_cols + ['source','ds']).copy()
    grp_keys = key_cols + ['source']
    def z_of(s: pd.Series):
        mu = s.rolling(7, min_periods=3).mean()
        sd = s.rolling(7, min_periods=3).std().replace(0, pd.NA)
        return (s - mu) / sd
    z = df_daily.groupby(grp_keys)['mean_score'].transform(z_of)
    out = df_daily.assign(surprise_src7=z).groupby(key_cols + ['ds'], as_index=False)['surprise_src7'].mean()
    return out

# ----------------------------- main -----------------------------
def run(days:int, limit:int, throttle_ms:int, tau_days:float, wl:float, wh:float, med:int, nan_policy:str, auth_yaml:str):
    engine = create_engine(DB_URL, future=True)
    ensure_tables(engine)

    # 讀資料
    docs = _fetch_docs(engine, days, limit)
    if not docs: print('沒有可用的文級數據。'); return
    df_docs = pd.DataFrame(docs, columns=['news_id','ds','doc_score'])

    ents = _fetch_entities_for_ids(engine, df_docs['news_id'].tolist(), chunk_size=800, throttle_ms=min(throttle_ms, 10))
    rows = []
    for nid, mjson in ents:
        try:
            arr = json.loads(mjson) if mjson else []
        except Exception:
            arr = []
        for it in arr:
            rows.append({'news_id': int(nid), 'ticker': it.get('ticker') or '', 'industry': it.get('industry') or ''})
    df_map = pd.DataFrame(rows) if rows else pd.DataFrame(columns=['news_id','ticker','industry'])

    meta = _fetch_meta_for_ids(engine, df_docs['news_id'].tolist(), chunk_size=800, throttle_ms=min(throttle_ms, 10))
    df_meta = pd.DataFrame(meta, columns=['news_id','source','pub_date']) if meta else pd.DataFrame(columns=['news_id','source','pub_date'])

    # join & weights
    df_join = df_docs.merge(df_meta, on='news_id', how='left')
    auth_default, auth_table = _load_authority(auth_yaml)
    df_join['w'] = _apply_weights(df_join, auth_default, auth_table, tau_days)

    # ---------- Entity 層 ----------
    df_ent = df_join.merge(df_map[['news_id','ticker']], on='news_id', how='left').dropna(subset=['ticker'])
    if not df_ent.empty:
        agg_ent = df_ent.groupby(['ticker','ds'], as_index=False).agg(
            n_docs=('doc_score','size'),
            mean_score=('doc_score','mean'),
            weighted_mean=('doc_score', lambda s: float((s * df_ent.loc[s.index, 'w']).sum() / max(df_ent.loc[s.index, 'w'].sum(), 1e-9)))
        )
        agg_ent = _denoise_inplace(agg_ent, 'ticker', wl, wh, med)
        agg_ent = _calc_rollings(agg_ent, 'ticker')
        tmp = df_ent.groupby(['ticker','source','ds'], as_index=False)['doc_score'].mean().rename(columns={'doc_score':'mean_score'})
        sps = _calc_surprise(tmp, ['ticker'])
        agg_ent = agg_ent.merge(sps, on=['ticker','ds'], how='left')
        with engine.begin() as conn:
            for _, r in agg_ent.iterrows():
                payload = {
                    'tk': r['ticker'], 'ds': r['ds'], 'n': int(r['n_docs']),
                    'm': _san(r['mean_score'], nan_policy),
                    'wm': _san(r.get('weighted_mean'), nan_policy),
                    'e': _san(r['ewma_20'], nan_policy),
                    'z': _san(r['zscore_30'], nan_policy),
                    'c': _san(r['cum30'], nan_policy),
                    'sp': _san(r.get('surprise_src7'), nan_policy),
                }
                conn.execute(text("""
                    MERGE signals_entity_daily AS t
                    USING (SELECT :tk AS ticker, :ds AS ds) AS src
                    ON (t.ticker=src.ticker AND t.ds=src.ds)
                    WHEN MATCHED THEN UPDATE SET n_docs=:n, mean_score=:m, weighted_mean=:wm, ewma_20=:e, zscore_30=:z, cum30=:c, surprise_src7=:sp
                    WHEN NOT MATCHED THEN INSERT (ticker, ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7)
                    VALUES (:tk, :ds, :n, :m, :wm, :e, :z, :c, :sp);
                """), payload)
                if throttle_ms>0: time.sleep(throttle_ms/1000.0)

    # ---------- Industry 層 ----------
    df_ind = df_join.merge(df_map[['news_id','industry']], on='news_id', how='left').dropna(subset=['industry'])
    if not df_ind.empty:
        agg_ind = df_ind.groupby(['industry','ds'], as_index=False).agg(
            n_docs=('doc_score','size'),
            mean_score=('doc_score','mean'),
            weighted_mean=('doc_score', lambda s: float((s * df_ind.loc[s.index, 'w']).sum() / max(df_ind.loc[s.index, 'w'].sum(), 1e-9)))
        )
        agg_ind = _denoise_inplace(agg_ind, 'industry', wl, wh, med)
        agg_ind = _calc_rollings(agg_ind, 'industry')
        tmp = df_ind.groupby(['industry','source','ds'], as_index=False)['doc_score'].mean().rename(columns={'doc_score':'mean_score'})
        sps = _calc_surprise(tmp, ['industry'])
        agg_ind = agg_ind.merge(sps, on=['industry','ds'], how='left')
        with engine.begin() as conn:
            for _, r in agg_ind.iterrows():
                payload = {
                    'ik': r['industry'], 'ds': r['ds'], 'n': int(r['n_docs']),
                    'm': _san(r['mean_score'], nan_policy),
                    'wm': _san(r.get('weighted_mean'), nan_policy),
                    'e': _san(r['ewma_20'], nan_policy),
                    'z': _san(r['zscore_30'], nan_policy),
                    'c': _san(r['cum30'], nan_policy),
                    'sp': _san(r.get('surprise_src7'), nan_policy),
                }
                conn.execute(text("""
                    MERGE signals_industry_daily AS t
                    USING (SELECT :ik AS industry, :ds AS ds) AS src
                    ON (t.industry=src.industry AND t.ds=src.ds)
                    WHEN MATCHED THEN UPDATE SET n_docs=:n, mean_score=:m, weighted_mean=:wm, ewma_20=:e, zscore_30=:z, cum30=:c, surprise_src7=:sp
                    WHEN NOT MATCHED THEN INSERT (industry, ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7)
                    VALUES (:ik, :ds, :n, :m, :wm, :e, :z, :c, :sp);
                """), payload)
                if throttle_ms>0: time.sleep(throttle_ms/1000.0)

    # ---------- Market 層 ----------
    agg_mkt = df_join.groupby(['ds'], as_index=False).agg(
        n_docs=('doc_score','size'),
        mean_score=('doc_score','mean'),
        weighted_mean=('doc_score', lambda s: float((s * df_join.loc[s.index, 'w']).sum() / max(df_join.loc[s.index, 'w'].sum(), 1e-9)))
    ).sort_values('ds')
    # 去噪（市場層無 key）
    agg_mkt['mean_score'] = _median_filter(_winsorize(agg_mkt['mean_score'], wl, wh), med)
    # rolling 與 zscore
    rm = agg_mkt['mean_score'].rolling(30, min_periods=5).mean()
    rs = agg_mkt['mean_score'].rolling(30, min_periods=5).std().replace(0, pd.NA)
    agg_mkt['ewma_20']   = agg_mkt['mean_score'].ewm(span=20, adjust=False).mean()
    agg_mkt['zscore_30'] = (agg_mkt['mean_score'] - rm) / rs
    agg_mkt['cum30']     = agg_mkt['mean_score'].rolling(30, min_periods=1).sum()
    # 驚奇度 by source
    tmp = df_join.groupby(['source','ds'], as_index=False)['doc_score'].mean().rename(columns={'doc_score':'mean_score'})
    sps = _calc_surprise(tmp, [])
    agg_mkt = agg_mkt.merge(sps, on=['ds'], how='left')
    with engine.begin() as conn:
        for _, r in agg_mkt.iterrows():
            payload = {
                'ds': r['ds'], 'n': int(r['n_docs']),
                'm': _san(r['mean_score'], nan_policy),
                'wm': _san(r.get('weighted_mean'), nan_policy),
                'e': _san(r['ewma_20'], nan_policy),
                'z': _san(r['zscore_30'], nan_policy),
                'c': _san(r['cum30'], nan_policy),
                'sp': _san(r.get('surprise_src7'), nan_policy),
            }
            conn.execute(text("""
                MERGE signals_market_daily AS t
                USING (SELECT :ds AS ds) AS src
                ON (t.ds=src.ds)
                WHEN MATCHED THEN UPDATE SET n_docs=:n, mean_score=:m, weighted_mean=:wm, ewma_20=:e, zscore_30=:z, cum30=:c, surprise_src7=:sp
                WHEN NOT MATCHED THEN INSERT (ds, n_docs, mean_score, weighted_mean, ewma_20, zscore_30, cum30, surprise_src7)
                VALUES (:ds, :n, :m, :wm, :e, :z, :c, :sp);
            """), payload)
            if throttle_ms>0: time.sleep(throttle_ms/1000.0)

    print('Signals 已更新完成。')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=120)
    ap.add_argument('--limit', type=int, default=50000)
    ap.add_argument('--throttle-ms', type=int, default=0)
    ap.add_argument('--tau-days', type=float, default=30.0)
    ap.add_argument('--winsor-low', type=float, default=0.05)
    ap.add_argument('--winsor-high', type=float, default=0.95)
    ap.add_argument('--median-window', type=int, default=3)
    ap.add_argument('--nan-policy', choices=['null','zero'], default='null')
    ap.add_argument('--authority-yaml', type=str, default='data/sources/authority.yaml')
    args = ap.parse_args()
    run(days=args.days, limit=args.limit, throttle_ms=args.throttle_ms,
        tau_days=args.tau_days, wl=args.winsor_low, wh=args.winsor_high, med=args.median_window,
        nan_policy=args.nan_policy, auth_yaml=args.authority_yaml)
