#!/usr/bin/env python3
"""mkcontent.py <out.json> <htmlfile>"""
import json, pathlib, sys
out, f = sys.argv[1], sys.argv[2]
c = pathlib.Path(f).read_text(encoding='utf-8')
pathlib.Path(out).write_text(json.dumps({'content': c}, ensure_ascii=False), encoding='utf-8')
