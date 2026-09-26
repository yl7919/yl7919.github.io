function Meta(m)
  if not quarto.doc.is_format("html") or m.translation == nil then return m end
  local base = "https://yl7919.github.io"
  local zh = pandoc.utils.stringify(m.lang or "en"):match("^zh") ~= nil
  local function urlof(p) p = "/" .. p:gsub("^/", ""); return (p:gsub("/index%.html$", "/")) end
  local here = urlof(quarto.doc.project_output_file())          -- verified available in 1.10.18, e.g. "zh/index.html"
  local other = urlof(pandoc.utils.stringify(m.translation))
  local en, zhurl = zh and other or here, zh and here or other
  quarto.doc.include_text("in-header", string.format(
    '<link rel="alternate" hreflang="en" href="%s%s">\n<link rel="alternate" hreflang="zh-Hans" href="%s%s">\n<link rel="alternate" hreflang="x-default" href="%s%s">', base, en, base, zhurl, base, en))
  return m
end
