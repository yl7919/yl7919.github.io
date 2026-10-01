-- Structured data for search engines and LLM crawlers (SEO plan 2026-10-01, items 4 and 8).
--   * pages with `jsonld-person: true` (the two home pages) get schema.org Person + WebSite;
--   * pages with a `citation:` block (the five papers, EN and ZH) get a ScholarlyArticle.
-- Facts come from the page metadata and _variables.yml-backed constants below; nothing private.
local BASE = "https://mingyangliu.org"
local PERSON_ID = BASE .. "/#person"

local function str(x) if x == nil then return nil end return pandoc.utils.stringify(x) end
local function urlof(p) p = "/" .. p:gsub("^/", ""); return (p:gsub("/index%.html$", "/")) end

local function person(zh)
  return {
    ["@type"] = "Person", ["@id"] = PERSON_ID,
    name = "Mingyang Liu", givenName = "Mingyang", familyName = "Liu",
    alternateName = { "Yang Liu", "Liu Mingyang", "刘明杨", "刘杨" },
    description = zh and "刘明杨：实证资产定价、基于特征的因子模型、投资组合选择。帝国理工学院金融学博士。"
      or "Mingyang Liu: empirical asset pricing, characteristic-based factor models, portfolio choice. PhD in Finance, Imperial College London.",
    jobTitle = zh and "访问研究员" or "Visiting Researcher",
    affiliation = { ["@type"] = "Organization", name = "Imperial Centre of Excellence in Quantitative Finance, Imperial College London",
      url = "https://www.imperial.ac.uk/quantitative-finance-centre/" },
    alumniOf = {
      { ["@type"] = "CollegeOrUniversity", name = "Imperial College London", url = "https://www.imperial.ac.uk/" },
      { ["@type"] = "CollegeOrUniversity", name = "Columbia University", url = "https://www.columbia.edu/" },
      { ["@type"] = "CollegeOrUniversity", name = "University of Michigan", url = "https://umich.edu/" },
    },
    knowsAbout = { "Empirical asset pricing", "Characteristic-based factor models", "Portfolio choice",
      "Machine learning in finance", "Financial econometrics" },
    url = BASE .. "/", image = BASE .. "/assets/img/portrait-640.jpg",
    email = "mailto:yang.liu19@imperial.ac.uk",
    sameAs = { "https://orcid.org/0009-0008-5418-2563", "https://profiles.imperial.ac.uk/yang.liu19",
      "https://www.linkedin.com/in/mingyang-buweinan/", "https://www.pexels.com/@Mingyang-LIU-301813241" },
  }
end

local function website(zh)
  return {
    ["@type"] = "WebSite", ["@id"] = BASE .. "/#website", url = BASE .. "/",
    name = zh and "刘明杨" or "Mingyang Liu", alternateName = zh and "Mingyang Liu" or "刘明杨",
    inLanguage = { "en", "zh-Hans" }, author = { ["@id"] = PERSON_ID },
  }
end

local function article(m, here, zh)
  local a = {
    ["@type"] = "ScholarlyArticle", headline = str(m.title), name = str(m.title),
    description = str(m.description), url = here, inLanguage = zh and "zh-Hans" or "en",
    isAccessibleForFree = true, author = { ["@id"] = PERSON_ID },
    publisher = { ["@type"] = "Organization", name = "Imperial Business School, Imperial College London" },
    mainEntityOfPage = here,
  }
  -- `date` reaches filters already formatted ("September 2026"); read the ISO date from the source front matter instead
  local iso
  local fh = io.open(quarto.doc.input_file, "r")
  if fh then
    local head = fh:read(4000); fh:close()
    iso = head and head:match("\ndate:%s*\"?(%d%d%d%d%-%d%d%-%d%d)")
  end
  if not iso and m.date then
    local d = str(m.date)
    local y, mo = d:match("(%d%d%d%d)年(%d+)月")
    if y then iso = string.format("%s-%02d", y, tonumber(mo)) else iso = d end
  end
  a.datePublished = iso
  if m.subtitle then a.alternativeHeadline = str(m.subtitle) end
  if m.downloads and type(m.downloads) == "table" then
    for _, d in ipairs(m.downloads) do
      local href = str(d.href)
      if href and href:match("%.pdf$") and not a.encoding then
        if href:sub(1, 1) == "/" then href = BASE .. href end
        a.encoding = { ["@type"] = "MediaObject", encodingFormat = "application/pdf", contentUrl = href }
      end
    end
  end
  if m.ssrn then a.sameAs = str(m.ssrn) end
  return a
end

function Meta(m)
  if not quarto.doc.is_format("html") then return m end
  local zh = (str(m.lang) or "en"):match("^zh") ~= nil
  local here = BASE .. urlof(quarto.doc.project_output_file())
  local graph = {}
  if m["jsonld-person"] then
    table.insert(graph, person(zh)); table.insert(graph, website(zh))
  end
  if m.citation then table.insert(graph, article(m, here, zh)) end
  if #graph == 0 then return m end
  local doc = { ["@context"] = "https://schema.org", ["@graph"] = graph }
  quarto.doc.include_text("in-header", '<script type="application/ld+json">' .. quarto.json.encode(doc) .. '</script>')
  return m
end
