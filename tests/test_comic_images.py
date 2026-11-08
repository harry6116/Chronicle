import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from chronicle_app.services.comic_images import append_comic_detail_views, comic_generation_config
from chronicle_app.services.processing_runtime import build_payload


class ComicImagesTest(unittest.TestCase):
    def test_real_grid_crops_preserve_colour_and_do_not_change_source(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-c", '''
import io,json,sys
from pathlib import Path
from PIL import Image,ImageDraw
from chronicle_app.services.comic_images import detect_comic_regions,build_comic_detail_views
image=Image.new("RGB",(600,800),"white")
draw=ImageDraw.Draw(image)
for box in [(20,20,290,380),(310,20,580,380),(20,410,290,780),(310,410,580,780)]:
    draw.rectangle(box,fill=(220,30,60),outline="black",width=4)
path=Path(sys.argv[1])/"grid.png"
image.save(path)
original=path.read_bytes()
regions=detect_comic_regions(image)
views=build_comic_detail_views(path)
assert len(regions)==4 and len(views)==12
for label,data in views[::3]:
    assert "provisional" in label and "not a prescribed panel count" in label
    with Image.open(io.BytesIO(data)) as crop:
        r,g,b=crop.getpixel((100,100))
        assert r>g+100 and r>b+100
assert path.read_bytes()==original
assert detect_comic_regions(Image.new("RGB",(600,800),"white"))==[]
print(json.dumps({"regions":len(regions),"views":len(views)}))
''', directory], capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"regions": 4, "views": 12})

    def test_other_provider_payloads_retain_overview_and_add_only_detail_images(self):
        for model in ("gpt-4o", "claude-sonnet-4-6"):
            with self.subTest(model=model), patch("chronicle_app.services.comic_images.build_comic_detail_views", return_value=[("Same page detail", b"disposable-image")]):
                overview = [{"type": "text", "text": "Original overview"}]
                result = append_comic_detail_views(overview, "source.png", model, build_payload)
                self.assertEqual(overview, [{"type": "text", "text": "Original overview"}])
                self.assertEqual(result[0], overview[0])
                self.assertEqual(len(result), 3)

    def test_no_detected_regions_keep_existing_request(self):
        original = ["Original overview"]
        with patch("chronicle_app.services.comic_images.build_comic_detail_views", return_value=[]):
            self.assertIs(append_comic_detail_views(original, "source.png", "gemini-2.5-pro", None), original)

    def test_only_comic_generation_changes_temperature(self):
        self.assertEqual(comic_generation_config(["Handwritten letter"]), {})
        self.assertEqual(comic_generation_config(["COMICS / MANGA / GRAPHIC NOVELS RULES:"], "gemini-3.1-pro-preview"), {})
        self.assertEqual(comic_generation_config(["COMICS / MANGA / GRAPHIC NOVELS RULES:"], "gemini-3.8-flash"), {})
        self.assertEqual(comic_generation_config([object(), "COMICS / MANGA / GRAPHIC NOVELS RULES:"]), {"temperature": 0})
