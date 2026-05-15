import unittest

from chronicle_core import apply_expanded_abbreviations


class MilitaryAbbreviationExpansionTest(unittest.TestCase):
    def test_expands_commonwealth_war_diary_and_casualty_terms(self):
        text = "15th Inf Bde AIF: OC reported Pte Jones WIA at RAP, then TOS by 21st Bn."

        expanded = apply_expanded_abbreviations(text)

        self.assertIn("15th Infantry Brigade Australian Imperial Force", expanded)
        self.assertIn("Officer Commanding reported Private Jones Wounded in Action", expanded)
        self.assertIn("Regimental Aid Post", expanded)
        self.assertIn("Taken on Strength by 21st Battalion", expanded)

    def test_expands_us_naval_air_and_theater_terms(self):
        text = "USAAF det moved from ETO to PTO; LST and LVT support followed USMC orders."

        expanded = apply_expanded_abbreviations(text)

        self.assertIn("United States Army Air Forces Detachment", expanded)
        self.assertIn("European Theater of Operations", expanded)
        self.assertIn("Pacific Theater of Operations", expanded)
        self.assertIn("Landing Ship, Tank", expanded)
        self.assertIn("Landing Vehicle, Tracked", expanded)
        self.assertIn("United States Marine Corps", expanded)

    def test_expands_german_french_and_japanese_terms(self):
        text = "OKH listed Pz Abt and Hptm Muller; GQG noted Cie losses; IJN report followed."

        expanded = apply_expanded_abbreviations(text)

        self.assertIn("Oberkommando des Heeres", expanded)
        self.assertIn("Panzer Abteilung", expanded)
        self.assertIn("Hauptmann Muller", expanded)
        self.assertIn("Grand Quartier Général", expanded)
        self.assertIn("Compagnie losses", expanded)
        self.assertIn("Imperial Japanese Navy", expanded)

    def test_does_not_rewrite_html_tags_or_attributes(self):
        html = '<div class="Bde"><p>Div HQ and Bde moved.</p></div>'

        expanded = apply_expanded_abbreviations(html)

        self.assertIn('<div class="Bde">', expanded)
        self.assertIn("</div>", expanded)
        self.assertIn("<p>Division Headquarters and Brigade moved.</p>", expanded)

    def test_short_acronyms_do_not_expand_lowercase_words(self):
        text = "re the file: the nurse was an rn, not RN; MP and RE were listed separately."

        expanded = apply_expanded_abbreviations(text)

        self.assertIn("re the file", expanded)
        self.assertIn("an rn", expanded)
        self.assertIn("not Royal Navy", expanded)
        self.assertIn("Military Police and Royal Engineers", expanded)

    def test_newspaper_profile_uses_newspaper_glossary(self):
        text = "Rev. Smith sailed on SS Orontes, arr. Sydney ult.; AP later reported GDP changes."

        expanded = apply_expanded_abbreviations(text, "newspaper")

        self.assertIn("Reverend Smith", expanded)
        self.assertIn("Steamship Orontes", expanded)
        self.assertIn("arrived Sydney last month", expanded)
        self.assertIn("Associated Press later reported Gross Domestic Product", expanded)

    def test_medical_profile_keeps_military_acronyms_out(self):
        text = "BP and ECG noted; RN and MP were copied from the source."

        expanded = apply_expanded_abbreviations(text, "medical")

        self.assertIn("blood pressure and electrocardiogram noted", expanded)
        self.assertIn("RN and MP were copied", expanded)
        self.assertNotIn("Royal Navy", expanded)
        self.assertNotIn("Military Police", expanded)


if __name__ == "__main__":
    unittest.main()
