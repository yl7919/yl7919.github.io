-- filters/vars-optional.lua — drop table rows whose value is unknown (spec "Home page" §5,
-- "Error handling: missing owner variables"). Runs after `quarto`, so {{< var >}} is expanded:
-- an empty variable renders as "", an unset one as bold "?var:name". Rows whose second cell
-- stringifies to "" or starts with "?var:" are removed; a table left with no rows is dropped.
--
-- Scope: only two-column tables (label · value), the shape of the contact table. Results
-- tables (research/_tbl-*.md) and CV tables have more columns and are never touched.
-- A row dropped for an unset variable ("?var:name") is reported in the render log so a
-- misspelled key cannot disappear silently; an empty variable is an intentional omission.

local function cell_text(cell)
  if cell == nil then return "" end
  return pandoc.utils.stringify(cell.contents or cell)
end

local function trim(text)
  return (text:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function optional_value(text)
  text = trim(text)
  return text == "" or text:sub(1, 5) == "?var:"
end

local function warn(msg)
  if quarto and quarto.log and quarto.log.warning then quarto.log.warning(msg) else io.stderr:write("WARNING: " .. msg .. "\n") end
end

local function keep_row(row)
  local cells = row.cells or row
  if #cells < 2 then return true end
  local value = trim(cell_text(cells[2]))
  if not optional_value(value) then return true end
  if value:sub(1, 5) == "?var:" then
    warn(string.format('vars-optional: dropped row "%s" — variable %s is not set in _variables.yml',
      trim(cell_text(cells[1])), value))
  end
  return false
end

function Table(tbl)
  if #tbl.colspecs ~= 2 then return nil end
  local kept_any = false
  for _, body in ipairs(tbl.bodies) do
    local rows = pandoc.List({})
    for _, row in ipairs(body.body) do
      if keep_row(row) then rows:insert(row) end
    end
    body.body = rows
    if #rows > 0 then kept_any = true end
  end
  if not kept_any then return {} end
  return tbl
end
