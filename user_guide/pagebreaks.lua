-- pagebreaks.lua
-- Conditional page breaks for pandoc → LaTeX User Guide builds.
--
-- Usage:
--   pandoc --lua-filter pagebreaks.lua --metadata paper_format=b5 ...
--
-- Between-block page breaks (fenced divs in markdown):
--   ::: pagebreak            fires for every format
--   ::: pagebreak-a4         fires for A4 builds only
--   ::: pagebreak-b5         fires for B5 builds only
--   :::
--
-- Inside code-block breaks:
--   !!! yaml-cbreak-a4       fires for A4 builds only
--   !!! text-cbreak-b5       fires for B5 builds only
--
-- The prefix before -cbreak- sets the language class of the code block that
-- follows the break (e.g. yaml, text, toml) for correct syntax highlighting.
-- Marker lines are always stripped from the output; a \newpage is inserted
-- only for the active format.  In non-LaTeX output all markers are just removed.
--
-- Implementation note: pandoc's Lua filter traversal is bottom-up, so a plain
-- Meta function would run AFTER CodeBlock functions, leaving paper_format nil.
-- We use a Pandoc function instead, which receives the full document and lets
-- us read metadata before walking any elements.

local function newpage()
  return pandoc.RawBlock("latex", "\\newpage")
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Between-block page breaks via fenced divs
--
-- Required syntax — the closing ::: is mandatory:
--   ::: pagebreak
--   :::
--
-- If the closing ::: is accidentally omitted, pandoc parses everything
-- that follows as children of the div.  The handler always re-emits
-- el.content after the \newpage so that the document is never truncated.
-- ──────────────────────────────────────────────────────────────────────────────
local function make_div_filter(paper_format)
  return function(el)
    local function emit(active)
      if active then
        if FORMAT == "latex" then
          -- Prepend \newpage; re-emit any children so a missing ::: is safe.
          local result = pandoc.List({newpage()})
          result:extend(el.content)
          return result
        else
          return el.content  -- non-latex: strip the div tag, keep content
        end
      else
        return el.content    -- wrong format: strip the div tag, keep content
      end
    end

    for _, class in ipairs(el.classes) do
      if class == "pagebreak" then
        return emit(true)
      elseif class == "pagebreak-" .. paper_format then
        return emit(true)
      elseif class:match("^pagebreak%-") then
        return emit(false)
      end
    end
  end
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Inside-code-block conditional breaks
--
-- Recognises lines of the form (anywhere inside a fenced code block):
--   !!! <lang>-cbreak-<format>
--
-- <lang>   — the language identifier to apply to the code block that FOLLOWS
--            the break (e.g. yaml, text, toml).  It is used to set the syntax-
--            highlighting class of the new sub-block, so it must match the
--            intended language of the content after the split.
-- <format> — the paper format that activates this break (a4 or b5).
--
-- The CodeBlock handler splits the block at active-format markers and strips
-- all other format markers.  Multiple CodeBlocks are returned interleaved with
-- \newpage RawBlocks when a split occurs.  Each sub-block receives the language
-- class from the marker that introduced it; the first sub-block keeps the
-- original block's language class.
-- ──────────────────────────────────────────────────────────────────────────────
local CBREAK = "^%s*!!!%s+(.-)%-cbreak%-([%w_]+)%s*$"

local function make_codeblock_filter(paper_format)
  return function(el)
    local orig_lang = el.classes[1] or ""
    local segments = {{lang = orig_lang, lines = {}}}
    local has_marker = false

    for line in (el.text .. "\n"):gmatch("([^\n]*)\n") do
      local lang, fmt = line:match(CBREAK)
      if lang and fmt then
        has_marker = true
        if fmt == paper_format and FORMAT == "latex" then
          -- Start a new segment; the prefix sets its language class.
          table.insert(segments, {lang = lang, lines = {}})
        end
        -- Always strip the marker line from the output.
      else
        table.insert(segments[#segments].lines, line)
      end
    end

    if not has_marker then return nil end  -- block unchanged

    if #segments == 1 then
      -- Markers were stripped but no split occurred (inactive format).
      el.text = table.concat(segments[1].lines, "\n")
      return el
    end

    local result = pandoc.List()
    for i, seg in ipairs(segments) do
      if i > 1 then result:insert(newpage()) end
      local cb = el:clone()
      cb.text = table.concat(seg.lines, "\n")
      -- Apply the language class from the marker prefix.
      if seg.lang ~= "" then
        cb.classes[1] = seg.lang
      else
        cb.classes = pandoc.List()
      end
      result:insert(cb)
    end
    return result
  end
end

-- ──────────────────────────────────────────────────────────────────────────────
-- Top-level Pandoc function — runs before any element walking, so metadata is
-- available when Div and CodeBlock handlers are called.
-- ──────────────────────────────────────────────────────────────────────────────
function Pandoc(doc)
  local paper_format = ""
  if doc.meta.paper_format then
    paper_format = pandoc.utils.stringify(doc.meta.paper_format)
  end

  return doc:walk({
    Div       = make_div_filter(paper_format),
    CodeBlock = make_codeblock_filter(paper_format),
  })
end
