"""Portable application-state oracle; file hashes remain artifact custody checks."""
import sqlite3
from pathlib import Path


def logical_state(path):
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as conn:
        schema=conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        tables=[r[1] for r in schema if r[0]=='table']
        values={}
        for name in tables:
            quoted='"'+name.replace('"','""')+'"'
            values[name]=conn.execute('SELECT rowid,* FROM '+quoted+' ORDER BY rowid').fetchall()
        return {'schema':schema,'tables':values}
