#!/usr/bin/env python3
"""构造 WP pages 的发布 body：mkbody.py <out> <title> <slug> <parent> <htmlfile>"""
import json
import pathlib
import sys

out, title, slug, parent, htmlfile = sys.argv[1:6]
content = pathlib.Path(htmlfile).read_text(encoding='utf-8')
body = {'title': title, 'slug': slug, 'parent': int(parent),
        'content': content, 'status': 'publish'}
pathlib.Path(out).write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')
print('body ->', out, 'title=', title, 'slug=', slug, 'parent=', parent)
