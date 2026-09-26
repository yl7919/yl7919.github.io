-- filters/paperhead.lua — Distill-style page head (spec D2, "Research pages").
-- Runs after Quarto's own filters (filters: [quarto, filters/paperhead.lua, ...]),
-- so {{< var >}} shortcodes in metadata are already expanded.
--
-- 1. `jmp: {title, href}` (home page)  -> <div class="jmp-line"><span class="tag jmp">Job market paper</span> <a>title</a></div>
-- 2. `downloads: [{label, href}, ...]` -> <div class="paper-downloads">Link · Link · ...</div>
--    Entries whose href stringifies to "" or starts with "?var:" (unset variable) are dropped.
-- 3. A <div class="d-contents"> (Distill contents) built from body headers of level 2..toc-depth,
--    headed "Contents" (or "目录" when meta.lang starts with "zh"). Quarto strips `toc-depth`
--    and `number-sections` from meta before user filters run, so toc-depth is read from
--    PANDOC_WRITER_OPTIONS and "this is a numbered paper page" is detected from the
--    .header-section-number spans Quarto has already placed in the headers. Emitted when the
--    page is numbered (`number-sections: true`) or sets `contents: true`; `contents: false` suppresses it.
-- All three are inserted at the top of the body, so the rendered order is
-- title block -> [jmp-line] -> paper-downloads -> d-contents -> body.

local function str(x)
  if x == nil then return "" end
  return pandoc.utils.stringify(x)
end

local function usable_href(href)
  return href ~= "" and href:sub(1, 5) ~= "?var:"
end

local function inlines_of(v)
  -- Metadata values arrive as Inlines (MetaInlines) or strings (MetaString).
  if type(v) == "string" then return pandoc.Inlines({ pandoc.Str(v) }) end
  if v == nil then return pandoc.Inlines({}) end
  if v.t == "MetaInlines" or (type(v) == "table" and v[1] ~= nil and v[1].t ~= nil) then
    return pandoc.Inlines(v)
  end
  return pandoc.Inlines({ pandoc.Str(str(v)) })
end

local function is_true(v)
  if type(v) == "boolean" then return v end
  return str(v) == "true"
end

local function jmp_line(meta)
  local jmp = meta.jmp
  if type(jmp) ~= "table" or jmp.title == nil or jmp.href == nil then return nil end
  local href = str(jmp.href)
  if not usable_href(href) then return nil end
  local tag = pandoc.Span({ pandoc.Str("Job"), pandoc.Space(), pandoc.Str("market"), pandoc.Space(), pandoc.Str("paper") },
    pandoc.Attr("", { "tag", "jmp" }))
  local link = pandoc.Link(inlines_of(jmp.title), href)
  return pandoc.Div(pandoc.Para({ tag, pandoc.Space(), link }), pandoc.Attr("", { "jmp-line" }))
end

local function downloads_row(meta)
  local list = meta.downloads
  if type(list) ~= "table" then return nil end
  local inl = pandoc.Inlines({})
  local n = 0
  for _, entry in ipairs(list) do
    if type(entry) == "table" then
      local href = str(entry.href)
      if usable_href(href) then
        if n > 0 then
          inl:insert(pandoc.Space()); inl:insert(pandoc.Str("·")); inl:insert(pandoc.Space())
        end
        inl:insert(pandoc.Link(inlines_of(entry.label), href))
        n = n + 1
      end
    end
  end
  if n == 0 then return nil end
  return pandoc.Div(pandoc.Para(inl), pandoc.Attr("", { "paper-downloads" }))
end

local function header_inlines(h)
  -- Copy the header text without any section-number span.
  local out = pandoc.Inlines({})
  for _, el in ipairs(h.content) do
    if not (el.t == "Span" and el.classes:includes("header-section-number")) then
      if not (#out == 0 and (el.t == "Space" or el.t == "SoftBreak")) then out:insert(el) end
    end
  end
  return out
end

local function numbered(h)
  local f = h.content[1]
  return f ~= nil and f.t == "Span" and f.classes:includes("header-section-number")
end

local function toc_depth(meta)
  local wo = PANDOC_WRITER_OPTIONS
  local d = (wo and tonumber(wo.toc_depth)) or tonumber(str(meta["toc-depth"])) or 3
  if d < 2 then d = 2 end
  return d
end

local function contents_nav(doc)
  local meta = doc.meta
  if meta.contents ~= nil and not is_true(meta.contents) then return nil end
  local depth = toc_depth(meta)

  -- Collect headers 2..depth in document order.
  local heads = {}
  doc:walk({
    Header = function(h)
      if h.level >= 2 and h.level <= depth and h.identifier ~= ""
         and not h.classes:includes("unlisted") then
        heads[#heads + 1] = h
      end
      return nil
    end
  })
  if #heads == 0 then return nil end
  if not is_true(meta.contents) then
    local any = false
    for _, h in ipairs(heads) do if numbered(h) then any = true; break end end
    if not any then return nil end
  end

  -- Build nested bullet lists with a level stack. Each stack entry is a list plus the
  -- header level of the items it holds (nil until the first item arrives).
  local root = pandoc.BulletList({})
  local stack = { { level = nil, list = root, last = nil } }
  for _, h in ipairs(heads) do
    while #stack > 1 and stack[#stack].level ~= nil and h.level < stack[#stack].level do
      table.remove(stack)
    end
    local top = stack[#stack]
    if top.level == nil then top.level = h.level end
    if h.level > top.level and top.last ~= nil then
      local sub = pandoc.BulletList({})
      top.last[#top.last + 1] = sub
      stack[#stack + 1] = { level = h.level, list = sub, last = nil }
      top = stack[#stack]
    end
    local item = { pandoc.Plain({ pandoc.Link(header_inlines(h), "#" .. h.identifier) }) }
    top.list.content:insert(item)
    top.last = item
  end

  local zh = str(meta.lang):match("^zh") ~= nil
  local label = zh and "目录" or "Contents"
  -- Raw <h3>: a pandoc Header here would be wrapped by --section-divs into a section.level3
  -- that swallows the .d-contents attributes (verified), and it must not be numbered or listed.
  local heading = pandoc.RawBlock("html", '<h3 class="d-contents-title">' .. label .. "</h3>")
  return pandoc.Div({ heading, root }, pandoc.Attr("", { "d-contents" }, { role = "navigation", ["aria-label"] = label }))
end

function Pandoc(doc)
  if not quarto.doc.is_format("html") then return doc end
  local head = {}
  local j = jmp_line(doc.meta);      if j then head[#head + 1] = j end
  local d = downloads_row(doc.meta); if d then head[#head + 1] = d end
  local c = contents_nav(doc);       if c then head[#head + 1] = c end
  if #head == 0 then return doc end
  local blocks = pandoc.Blocks({})
  for _, b in ipairs(head) do blocks:insert(b) end
  for _, b in ipairs(doc.blocks) do blocks:insert(b) end
  doc.blocks = blocks
  return doc
end
