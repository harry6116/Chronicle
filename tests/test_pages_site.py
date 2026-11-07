from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit, unquote
from bs4 import BeautifulSoup
from tools.build_pages_site import build_site

ROOT = Path(__file__).resolve().parents[1]


class PagesSiteTest(unittest.TestCase):
    def test_generated_site_has_working_local_links_and_only_public_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            output = (Path(directory) / 'site').resolve()
            build_site(ROOT, output)
            self.assertTrue((output / 'user-guide.html').is_file())
            disclaimer = BeautifulSoup((output / 'disclaimer.html').read_text(), 'html.parser')
            self.assertIn('Data Processing Boundary', disclaimer.get_text())
            self.assertNotIn('Skip to release notes', disclaimer.get_text())
            self.assertIn('provider retention policies', disclaimer.get_text())
            self.assertIsNotNone(disclaimer.find('a', href='https://ai.google.dev/gemini-api/terms'))
            for path in output.rglob('*'):
                if path.is_file():
                    self.assertIn(path.suffix, ('.html', '.png', '.jpg', '.jpeg', '.svg', ''))
                if path.suffix != '.html':
                    continue
                soup = BeautifulSoup(path.read_text(), 'html.parser')
                for node in soup.select('[href], [src]'):
                    url = urlsplit(node.get('href') or node.get('src'))
                    if url.scheme or url.netloc:
                        continue
                    target = (path.parent / unquote(url.path)).resolve() if url.path else path
                    self.assertTrue(target.is_relative_to(output), str(target))
                    self.assertTrue(target.is_file(), str(target))
                    if url.fragment and target.suffix == '.html':
                        document = BeautifulSoup(target.read_text(), 'html.parser')
                        self.assertIsNotNone(document.find(id=unquote(url.fragment)), str(target) + '#' + url.fragment)

    def test_nonempty_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'keep.txt'
            marker.write_text('keep')
            with self.assertRaises(ValueError):
                build_site(ROOT, directory)
            self.assertEqual(marker.read_text(), 'keep')


class PagesReleaseTest(unittest.TestCase):
    def release(self):
        return {
            'tag_name': 'v2.0.0', 'draft': False, 'prerelease': False,
            'html_url': 'https://github.com/harry6116/Chronicle/releases/tag/v2.0.0',
            'published_at': '2026-11-08T01:00:00Z',
            'body': '# Chronicle 2.0.0\n\n## Improvements\n\n- Improved reading order\n- Better keyboard navigation\n- Safer updates\n- More changes\n<script>unsafe</script>',
            'assets': [{'name': name, 'state': 'uploaded', 'size': 100}
                       for name in ('Chronicle.mac.zip', 'Chronicle.windows.zip')],
        }

    def test_release_announcement_and_full_notes_are_generated_without_active_html(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'site'
            build_site(ROOT, output, release=self.release())
            soup = BeautifulSoup((output / 'index.html').read_text(), 'html.parser')
            announcement = soup.find(id='release-announcement')
            self.assertIn('Chronicle 2.0.0', announcement.get_text())
            self.assertEqual(len(announcement.select('li')), 3)
            self.assertEqual(announcement.time['datetime'], '2026-11-08')
            self.assertEqual(announcement.select_one('a')['href'], 'release-notes.html')
            notes = BeautifulSoup((output / 'release-notes.html').read_text(), 'html.parser')
            self.assertIn('More changes', notes.get_text())
            self.assertIn('<script>unsafe</script>', notes.get_text())
            self.assertIsNone(notes.find('script'))
            self.assertIsNotNone(notes.find('h2', string='Improvements'))
            self.assertEqual(len(notes.select('li')), 4)
            links = [a['href'] for a in soup.select('a[href]')]
            for name in ('Chronicle.mac.zip', 'Chronicle.windows.zip'):
                self.assertIn('https://github.com/harry6116/Chronicle/releases/latest/download/' + name, links)

    def test_unpublished_or_incomplete_release_never_produces_an_announcement(self):
        for change in ({'draft': True}, {'prerelease': True}, {'assets': []},
                       {'published_at': None}, {'tag_name': 'not-a-version'},
                       {'html_url': 'javascript:alert(1)'}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                release = self.release()
                release.update(change)
                output = Path(directory) / 'site'
                with self.assertRaises(ValueError):
                    build_site(ROOT, output, release=release)
                self.assertFalse(output.exists())

    def test_missing_release_metadata_uses_generic_latest_link_without_stale_version(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'site'
            build_site(ROOT, output)
            soup = BeautifulSoup((output / 'index.html').read_text(), 'html.parser')
            self.assertNotIn('Chronicle 1.1.3', soup.get_text())
            self.assertIn('latest release', soup.find(id='release-announcement').get_text().lower())
