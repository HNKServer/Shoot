#!/usr/bin/env python3
import argparse, json, sqlite3
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('database')
p.add_argument('--json', dest='json_out')
a=p.parse_args()
path=Path(a.database)
con=sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True)
tables={r[0] for r in con.execute("select name from sqlite_master where type='table'")}
if 'museum_contents_m' not in tables:
    raise SystemExit('museum_contents_m not found')
cols=[r[1] for r in con.execute('pragma table_info(museum_contents_m)')]
count=con.execute('select count(*) from museum_contents_m').fetchone()[0]
cats=con.execute('select museum_tab_category_id,count(*) from museum_contents_m group by museum_tab_category_id order by museum_tab_category_id').fetchall()
report={'database':str(path),'rows':count,'columns':cols,'categories':cats}
print(json.dumps(report,ensure_ascii=False,indent=2))
if a.json_out: Path(a.json_out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
