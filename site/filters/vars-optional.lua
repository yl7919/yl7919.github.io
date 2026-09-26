-- filters/vars-optional.lua — drop table rows whose value is unknown (spec "Home page" §5,
-- "Error handling: missing owner variables"). Runs after `quarto`, so {{< var >}} is expanded:
-- an empty variable renders as "", an unset one as bold "?var:name". Rows whose second cell
-- stringifies to "" or starts with "?var:" are removed; a table left with no rows is dropped.

local function cell_text(cell)
  if cell == nil then return "" end
  return pandoc.utils.stringify(cell.contents or cell)
end

local function optional_value(text)
  text = text:gsub("^%s+", ""):gsub("%s+$", "")
  return text == "" or text:sub(1, 5) == "?var:"
end

local function keep_row(row)
  local cells = row.cells or row
  if #cells < 2 then return true end
  return not optional_value(cell_text(cells[2]))
end

function Table(tbl)
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
