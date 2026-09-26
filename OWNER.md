# Owner runbook

Five procedures for maintaining https://yl7919.github.io. Paths are relative to the `web/` folder
(`/Volumes/Extreme P2/Claude_Project_PWS/web`) unless they start with `/`. Commands are for the macOS
Terminal. Python comes from the venv outside the drive: `PY=$HOME/.local/venvs/pws-web/bin/python`.

Ground rules that apply to all five:

- Work on a branch, never directly on `main`. Pushing to `main` publishes the site (`.github/workflows/publish.yml`).
- Never delete a file from the site. Move it to `_held/` with `git mv`. `_held/` is not published.
- Ignore `._*` files. macOS creates them on this drive; git ignores them and the site checks tolerate them.
- Every page lists **Mingyang Liu** as the only author. Do not serve a PDF whose first page prints other names.
- Where content is not ready, write "available on request" or "in preparation". Do not write TODO or TBD.

---

## 1. Add a photo

The gallery pipeline (`build_photos.py`, the `{{< gallery >}}` shortcode, WebP sizes) is scheduled for
Batch B and is not in the repo yet. Until it arrives, this is the manual procedure. The three city pages
(`site/photography/{ann-arbor,new-york,london}.qmd`) already set `lightbox: {match: auto, ...}`, so every
image on them opens in the lightbox.

1. Choose the photograph. There must be no identifiable people in it (O4).
2. Give it a descriptive name, `YYYY-MM-short-title.jpg`, for example `2023-05-thames-dusk.jpg`.
3. Make the web copy. This resizes the long edge to 1600 px and drops all EXIF, GPS and ICC metadata:
   ```sh
   mkdir -p site/assets/photos/london
   $PY - ~/Pictures/DSC01234.jpg site/assets/photos/london/2023-05-thames-dusk.jpg <<'EOF'
   import sys
   from PIL import Image, ImageOps
   src, dst = sys.argv[1], sys.argv[2]
   im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
   im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
   im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)   # no exif=, no icc_profile=
   print(dst, im.size)
   EOF
   ```
   Note the printed size (for example `(1600, 1067)`). The folder `site/assets/photos/**` is already
   published by `site/_quarto.yml`.
4. Open `site/photography/london.qmd`. If the page still shows the three lines
   `::: {.figcaption}` / `Gallery not yet published.` / `:::`, replace them with the photo. Otherwise
   add the photo below the last one:
   ```markdown
   ![Thames at dusk from the South Bank](/assets/photos/london/2023-05-thames-dusk.jpg){width=1600 height=1067 loading="lazy"}
   ```
   The text in brackets is the caption and the alt text. It is required: rule (k) fails the build
   without it. Use the width and height printed in step 3.
5. Run the checks (procedure 5) and look at the page:
   `cd site && quarto preview photography/london.qmd`. Click the photo: it should open in the lightbox.
6. Commit: `git add site/assets/photos/london/2023-05-thames-dusk.jpg site/photography/london.qmd && git commit -m "content(photo): London, Thames at dusk"`.

When `build_photos.py` lands, steps 2 to 4 become "drop the originals into
`/Volumes/Extreme P2/Claude_Project_PWS/photos_src/<city>/` and run the script".

## 2. Add a static-figure paper page

Model: `site/research/characteristic-space-metrics.qmd`. It is a paper page with PDFs, an abstract and
no interactive figure.

1. Copy the PDFs into the site. Always copy; never move files out of the source folders:
   `cp "/path/to/My_Paper.pdf" site/assets/pdfs/My_Paper.pdf`.
2. Read the first-page byline of every PDF you will label "Paper" or "Slides":
   `pdftotext -l 1 site/assets/pdfs/My_Paper.pdf - | head -15`.
   If any name other than Mingyang Liu is printed, stop. Do not serve that PDF; use the text
   "Manuscript available on request" instead.
3. Create the page: `cp site/research/characteristic-space-metrics.qmd site/research/my-paper.qmd`.
   Edit the front matter:
   - `title`, `description` (the first sentence of the abstract, verbatim), `date` and `date-modified`;
   - `author`: keep the single `Mingyang Liu` entry;
   - `byline_ok:` today's date. This records that you did step 2. Rule (h) fails without it and
     checks every Paper/Slides PDF again with `pdftotext`;
   - `downloads`: one `{label: "Paper (PDF)", href: /assets/pdfs/My_Paper.pdf}` per file. Put "Paper"
     or "Slides" in the label so rule (h) checks it. Use `{text: "... available on request"}` for
     items without a file;
   - `citation.url`: `https://yl7919.github.io/research/my-paper.html`.
4. Replace the body: `## Abstract` (verbatim), then the figures, then `## Data`. For each static figure,
   put the image in `site/assets/img/my-paper/` and use this unit. Rules (f), (j) and (k) check the
   title, the caption, the provenance span and the alt text:
   ```markdown
   ::: {#figure-my-paper-1 .column-page .dfigure role="figure" aria-labelledby="figure-my-paper-1-title"}
   <div class="dfigure-title" id="figure-my-paper-1-title"><strong>Figure 1: Short title.</strong> One sentence on what is plotted.</div>

   <img src="/assets/img/my-paper/figure-1.png" width="1600" height="900" alt="What the figure shows, in words" style="width:100%">

   <div class="figcaption">How to read it, in one or two sentences. <span class="provenance">Source: <em>My Paper</em>, working paper (draft September 2026), Figure 1.</span></div>
   :::
   ```
   Always use root paths (`/assets/...`, `/data/...`). Rule (d) rejects `../data` and `{{< include ../`.
5. Add the research-index card:
   - `cp site/_includes/_card-csm.qmd site/_includes/_card-my-paper.qmd` and edit the tag, date, title,
     sentence, links and thumbnail;
   - make the thumbnail 560 px wide:
     `pdftoppm -png -f 1 -l 1 -scale-to-x 560 -scale-to-y -1 site/assets/pdfs/My_Paper.pdf site/assets/img/thumbs/my-paper`
     (this writes `my-paper-1.png` or `my-paper-01.png`, depending on the page count; rename it to `my-paper.png`, or crop a figure instead);
   - add `{{< include /_includes/_card-my-paper.qmd >}}` under the right heading in
     `site/research/index.qmd`.
6. Chinese research index. Copy `site/_includes/_card-zh-csm.qmd` to `_card-zh-my-paper.qmd`. Keep
   the English title and mark it "（英文）", as the other rows are. Include it in
   `site/zh/research/index.qmd`.
7. Commit the English files first. Then set `translated-from:` in `site/zh/research/index.qmd` to
   `$(git rev-parse --short HEAD)` and commit that too (see procedure 3).
8. Run the checks (procedure 5).

## 3. Translate a page

Example: `site/research/x.qmd` → `site/zh/research/x.qmd`.

1. `mkdir -p site/zh/research && cp site/research/x.qmd site/zh/research/x.qmd`.
2. Translate the prose, the figure titles and the captions in the zh file:
   - keep every `{{< include ... >}}` line unchanged: figure controls switch to Chinese by themselves
     through `t()`;
   - keep the English axis labels. Add "图内坐标轴沿用论文的英文量纲名称。" to each figure caption;
   - navbar and footer labels are rewritten to Chinese by `site/tools/zh_labels.py` during the render.
     Do not edit them.
3. Add the pair of `translation:` keys:
   - `translation: /zh/research/x.html` in the English file;
   - `translation: /research/x.html` in the zh file.
   These keys produce the hreflang links and the 中文 / English toggle target. Rule (c) checks that the
   target exists.
4. Commit the English file: `git add site/research/x.qmd && git commit -m "content: link x to its Chinese translation"`.
5. Set `translated-from: <sha>` in the zh file's front matter, where `<sha>` is `git rev-parse --short HEAD`
   (the commit from step 4, which includes the latest English text).
6. In `site/zh/research/index.qmd` (and its `_includes/_card-zh-*.qmd`), point the row at the zh page
   and remove "（英文）".
7. Run `$PY site/tools/check_translations.py`. The new page must read `current`. Then run the full
   checks (procedure 5) and commit.

Later, whenever the English page changes, `check_translations.py` reports the zh page as `STALE`.
Update the translation, then repeat step 5 with the new HEAD.

## 4. Rotate a city plate

No plate is published yet. The duotone band, the `{{< cityband >}}` shortcode and `city_images.py` are
Batch B. Until they arrive, you can prepare and replace plate files with the treatment the spec fixes
(`docs/.../2026-09-26-distill-restyle-design.md`, "City sections"). These files are what the band will
display.

1. Choose a wide, face-free photograph (≥ 2400 px on the long edge) or one of the public-domain prints
   listed in the spec. Keep the original in
   `/Volumes/Extreme P2/Claude_Project_PWS/photos_src/cities/<city>/` (outside `web/`, never committed).
2. Note the city's colours from `site/assets/theme.scss`:
   - ann-arbor: `#2b2a26` / `#e9dcb8`
   - new-york: `#1f2430` / `#d9d4c7`
   - london: `#1f3a5f` / `#d7ddd8`
3. Generate the band (5:2) and strip (5:1) files. The arguments are: source, city, shadow, light,
   focus x, focus y (0 to 1), output folder.
   ```sh
   $PY - "/Volumes/Extreme P2/Claude_Project_PWS/photos_src/cities/london/london-thames-dusk.jpg" \
       london "#1f3a5f" "#d7ddd8" 0.5 0.5 site/assets/img/cities <<'EOF'
   import sys
   from pathlib import Path
   from PIL import Image, ImageEnhance, ImageFilter, ImageOps
   src, city, shadow, light, fx, fy, out = sys.argv[1:8]
   out = Path(out); out.mkdir(parents=True, exist_ok=True)
   im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
   for kind, ratio in (("", 5 / 2), ("-strip", 5 / 1)):
       band = ImageOps.fit(im, (1920, round(1920 / ratio)), Image.Resampling.LANCZOS, centering=(float(fx), float(fy)))
       band = ImageOps.colorize(ImageEnhance.Contrast(ImageOps.grayscale(band)).enhance(0.75), black=shadow, white=light)
       band = band.filter(ImageFilter.GaussianBlur(0.6))
       for w in (640, 1280, 1920):
           f = out / f"{city}{kind}-{w}.webp"
           band.resize((w, round(w / ratio)), Image.Resampling.LANCZOS).save(f, "WEBP", quality=68, method=6)
           print(f.name, f.stat().st_size // 1024, "KB")
       if kind == "":
           band.resize((1280, 512), Image.Resampling.LANCZOS).save(out / f"{city}-1280.jpg", "JPEG", quality=80)
   EOF
   ```
4. Check the printed sizes. `london-1920.webp` must be ≤ 150 KB and `london-strip-1920.webp` ≤ 60 KB.
   If a print with fine hatching is over budget, change `quality=68` to `quality=60` and run again.
5. Open `site/assets/img/cities/london-1920.webp` and look at it. The subject should sit where you want
   it. If not, adjust the focus values in step 3 and run again.
6. Rotating means running steps 3 to 5 again with the new source, so the file names stay the same.
   Commit the files: `git add site/assets/img/cities/london-* && git commit -m "content(city): new London plate"`.
   A plate may appear only on the photography pages. Rule (e) fails the build if `.city-band`
   appears anywhere else.

## 5. Run the checks

Run all of them before every commit you intend to publish:

1. Plug in the drive (`/Volumes/Extreme P2`). The data check reads the research release there.
2. From `web/`, run `tools/precommit.sh`. It stops at the first failure and runs, in order:
   - `pytest pipeline/tests -q`
   - `pipeline/build_data.py --check`: the committed JSON, Markdown and PNG match the release
   - `quarto render` of `site/`
   - `site/tools/check_links.py`: broken links and rules (a) to (k)
   - `site/tools/check_translations.py --strict`
   - the exhibit-4 migration diff: the portfolio-formation computing cells must equal the pre-migration
     ones after the allowed renames
3. Without the drive, `tools/precommit.sh --no-sources` runs everything except `build_data.py --check`.
   Without the flag the script fails; it never skips silently (D19).
4. It succeeds when it ends with `precommit: all checks passed`. `check_links.py` then prints
   `checked N pages, 0 broken references, 0 rule (a)-(k) failures`. A note counting "macOS AppleDouble
   companions" is expected on this drive.
5. If `check_links.py` fails, the first word of each line names the rule:

   | First word | Rule | What it means |
   |---|---|---|
   | `BROKEN` | link check | a link or asset does not resolve in `_site` |
   | `DOWNLOAD` | (a) | a `downloads:` href does not resolve |
   | `GALLERY` | (b) | a page uses `{{< gallery` without `lightbox: {match: auto}` |
   | `TRANSLATION` | (c) | a `translation:` target does not exist |
   | `INCLUDE-PATH` | (d) | a `.qmd` uses `../data` or `{{< include ../` |
   | `CITY-BAND` | (e) | a `.city-band` appears outside the photography pages |
   | `DFIGURE` | (f) | a `.dfigure` lacks its title or caption |
   | `DUPLICATE-CELL` | (g) | two OJS cells on one page share a name |
   | `BYLINE` | (h) | an author is missing from a PDF's page 1, or `byline_ok:` is missing |
   | `APPLEDOUBLE` | (i) | a `._*` file was published or linked |
   | `PROVENANCE` | (j) | a figure caption lacks a `.provenance` span naming a manuscript or release |
   | `IMG-ALT` | (k) | an `<img>` has no `alt` attribute |
   | `FRONT-MATTER` | setup | a page's YAML front matter does not parse |
6. You can run any single check on its own from `web/`, after a render:
   - `$PY site/tools/check_links.py`
   - `$PY site/tools/check_translations.py` (add `--strict` to fail on stale pages)
   - `$HOME/.local/venvs/pws-web/bin/pytest pipeline -q`
7. On GitHub, `.github/workflows/check.yml` repeats the render, `check_links.py` and
   `check_translations.py` (warnings only) on every pull request and on pushes to `main` and `restyle`.
   It never runs the Python pipeline.
