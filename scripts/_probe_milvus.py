import urllib.request, urllib.error

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        print('  redirect %d -> %s' % (code, newurl))
        return None
opener = urllib.request.build_opener(NoRedirect)

candidates = [
    'https://milvus.io/docs/schema',                 # no .md
    'https://milvus.io/docs/schema/',                # trailing slash
    'https://www.milvus.io/docs/schema.md',          # www
    'https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/userGuide/schema.md',  # GH raw
    'https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/userGuide/manage-collections/manage-collections.md',
    'https://raw.githubusercontent.com/milvus-io/milvus-docs/master/site/en/consistency.md',
]
for url in candidates:
    print('=== ', url)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research-kb-builder)'})
    try:
        r = opener.open(req, timeout=15)
        body = r.read()
        print('  OK', r.status, 'size', len(body), 'ctype', r.headers.get('Content-Type'))
    except urllib.error.HTTPError as e:
        print('  HTTPError', e.code, 'Location:', e.headers.get('Location'))
    except Exception as e:
        print('  ERR', type(e).__name__, e)
