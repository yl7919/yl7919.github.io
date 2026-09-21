# yl7919.github.io

Academic website of Mingyang Liu. Built with Quarto; interactive exhibits use Observable JS.

- `site/` — Quarto project (render with `quarto preview site`)
- `pipeline/` — Python scripts that turn research-release CSVs into `site/data/*.json`

Data on this site are aggregate portfolio-level results from the author's public research releases. The original stock panel is not redistributed.

## Deployment

Pushing to `main` triggers `.github/workflows/publish.yml`, which renders `site/` with Quarto and publishes to the `gh-pages` branch, served at https://yl7919.github.io. Data JSON files are committed; the pipeline is not run on CI. Before committing new data, run `$HOME/.local/venvs/pws-web/bin/python pipeline/build_data.py` and `$HOME/.local/venvs/pws-web/bin/pytest pipeline`.
