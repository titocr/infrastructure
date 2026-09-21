"""MkDocs hook: publish build provenance, then check generated local links."""
import json
import os
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])


def validate_links(site):
    site = Path(site).resolve()
    pages = {}
    for path in site.rglob('*.html'):
        parser = Links()
        parser.feed(path.read_text())
        pages[path] = parser
    errors = []
    for path, parser in pages.items():
        for href in parser.links:
            url = urlsplit(href)
            if url.scheme or url.netloc:
                continue
            target = ((site / unquote(url.path).lstrip('/')) if url.path.startswith('/')
                      else path.parent / unquote(url.path)).resolve() if url.path else path
            if target.is_dir():
                target = target / 'index.html'
            if not target.is_relative_to(site) or not target.exists():
                errors.append(f'{path.relative_to(site)}: missing {href}')
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f'{path.relative_to(site)}: missing anchor {href}')
    if errors:
        raise RuntimeError('Broken local links:\n' + '\n'.join(sorted(set(errors))))


def on_config(config):
    config.extra['manual_build'] = {
        'source_revision': os.environ.get('GUIDE_SOURCE_REVISION', 'unrecorded'),
        'source_sha256': os.environ.get('GUIDE_SOURCE_SHA256', 'unrecorded'),
        'source_modified': os.environ.get('GUIDE_SOURCE_MODIFIED', 'true') == 'true',
        'built_at_utc': os.environ.get('GUIDE_BUILD_TIME', 'unrecorded'),
    }
    return config


def on_post_build(config):
    # A new directory invalidates old cached workers AND their relative index requests.
    # Keep result links rooted at base_url; only the worker's asset location changes.
    search = Path(config.site_dir) / 'search'
    versioned = Path(config.site_dir) / ('search-' + config.extra['manual_build']['source_sha256'])
    shutil.copytree(search, versioned, dirs_exist_ok=True)
    script = versioned / 'main.js'
    content = script.read_text()
    if 'search/worker.js' not in content:
        raise RuntimeError('Review MkDocs search integration after dependency change')
    script.write_text(content.replace('search/worker.js', versioned.name + '/worker.js'))
    (Path(config.site_dir) / 'build-info.json').write_text(
        json.dumps(config.extra['manual_build'], indent=2) + '\n')
    validate_links(config.site_dir)
