"""Compare comic HTML with panel excerpts transcribed from the source scan."""

import argparse
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup, NavigableString


def extract_panels(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('nav, footer, script, style'):
        node.decompose()
    root = soup.find('main') or soup.body or soup
    panels = []
    active = None
    for node in root.descendants:
        if getattr(node, 'name', None) in {'h1', 'h2'}:
            active = None
            match = re.fullmatch(r'Panel\s+(\d+)(?:\s*[:.\-–—].*)?', node.get_text(' ', strip=True), re.I)
            if node.name == 'h2' and match:
                active = {'number': int(match[1]), 'parts': [], 'described': False}
                panels.append(active)
        elif active is not None and isinstance(node, NavigableString):
            if not node.find_parent(['h1', 'h2']):
                active['parts'].append(str(node))
        elif active is not None and getattr(node, 'name', None) == 'img':
            alt = str(node.get('alt', '')).strip()
            if alt and alt.lower() not in {'image', 'photo'}:
                active['described'] = True
                active['parts'].append(f'[Image Description: {alt}]')
    for panel in panels:
        panel['text'] = ' '.join(panel.pop('parts')).strip()
        description = r'\[(?:Image|Panel) Description:.*?\]'
        panel['described'] = panel['described'] or bool(re.search(description, panel['text'], re.I | re.S))
        panel['transcription'] = re.sub(description, '', panel['text'], flags=re.I | re.S).strip()
    return panels


def words(text):
    text = re.sub(r"(?<=\w)['’](?=\w)", '', text.casefold())
    return re.findall(r"\w+", text, flags=re.UNICODE)


def preamble_transcription(html):
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('nav, footer, script, style'):
        node.decompose()
    root = soup.find('main') or soup.body or soup
    parts = []
    for node in root.descendants:
        if getattr(node, 'name', None) == 'h2' and re.fullmatch(r'Panel\s+\d+(?:\s*[:.\-–—].*)?', node.get_text(' ', strip=True), re.I):
            break
        if isinstance(node, NavigableString):
            parts.append(str(node))
    return re.sub(r'\[(?:Image|Panel) Description:.*?\]', '', ' '.join(parts), flags=re.I | re.S)


def audit_reference(html, reference):
    expected = reference.get('panels', [])
    if not expected:
        raise ValueError('A reference must contain reviewed panel excerpts.')
    numbers = []
    for panel in expected:
        number = panel.get('number')
        excerpts = panel.get('excerpts')
        if not isinstance(number, int) or isinstance(number, bool) or number < 1 or number in numbers:
            raise ValueError('Reference panel numbers must be distinct positive integers.')
        if not isinstance(excerpts, list) or not excerpts or any(not isinstance(s, str) or not words(s) for s in excerpts):
            raise ValueError('Each reference panel needs nonempty source excerpts.')
        numbers.append(number)
    actual = extract_panels(html)
    preamble = reference.get('preamble_excerpts', [])
    if not isinstance(preamble, list) or any(not isinstance(s, str) or not words(s) for s in preamble):
        raise ValueError('Preamble excerpts must be a list of nonempty source excerpts.')
    preamble_tokens = words(preamble_transcription(html))
    missing_preamble = []
    for excerpt in preamble:
        wanted = words(excerpt)
        if not any(preamble_tokens[i:i + len(wanted)] == wanted for i in range(len(preamble_tokens) - len(wanted) + 1)):
            missing_preamble.append(excerpt)
    actual_numbers = [panel['number'] for panel in actual]
    missing = []
    for panel in expected:
        candidates = [p for p in actual if p['number'] == panel['number']]
        tokens = words(candidates[0]['transcription']) if len(candidates) == 1 else []
        for excerpt in panel['excerpts']:
            wanted = words(excerpt)
            if not any(tokens[i:i + len(wanted)] == wanted for i in range(len(tokens) - len(wanted) + 1)):
                missing.append({'panel': panel['number'], 'excerpt': excerpt})
    return {
        'scope': 'Selected source excerpts and panel order only; not a full transcription or visual accuracy score.',
        'expected_panel_order': numbers,
        'actual_panel_order': actual_numbers,
        'missing_excerpts': missing,
        'missing_preamble_excerpts': missing_preamble,
        'reference_checks_passed': numbers == actual_numbers and not missing and not missing_preamble,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('reference', type=Path, help='JSON with panels: [{number: 1, excerpts: ["source words"]}].')
    args = parser.parse_args()
    report = audit_reference(args.html.read_text(encoding='utf-8'), json.loads(args.reference.read_text(encoding='utf-8')))
    print(json.dumps(report, indent=2))
    return 0 if report['reference_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
