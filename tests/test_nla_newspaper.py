import unittest

from chronicle_app.services.nla_newspaper import (
    extract_nla_page_id,
    parse_trove_article_rendition,
    parse_trove_page_article_ids,
    strip_trove_tags,
)


class NlaNewspaperTest(unittest.TestCase):
    def test_extract_nla_page_id(self):
        self.assertEqual(extract_nla_page_id("https://nla.gov.au/nla.news-page12345"), "12345")
        self.assertIsNone(extract_nla_page_id("no page marker"))

    def test_strip_trove_tags_collapses_html_text(self):
        self.assertEqual(strip_trove_tags("<p>Hello<br> world !</p>"), "Hello world!")

    def test_parse_trove_page_article_ids_prefers_dom_ids_without_duplicates(self):
        html = '<div class="articleFromDB" id="article111"></div><div class="articleFromDB" id="article111"></div>'
        self.assertEqual(parse_trove_page_article_ids(html), ["111"])

    def test_parse_trove_article_rendition_discards_duplicate_title_paragraph(self):
        html = """
        <title>01 January 1900 - Local News.</title>
        <hr/>
        <div class='zone'><p>Local News.</p><p>Story body.</p><p>---</p></div>
        """

        title, paragraphs = parse_trove_article_rendition(html)

        self.assertEqual(title, "Local News")
        self.assertEqual(paragraphs, ["Story body."])


if __name__ == "__main__":
    unittest.main()
