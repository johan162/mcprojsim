local function header_text(cell)
    return pandoc.utils.stringify(cell.content)
end

function Table(element)
    if FORMAT ~= "latex" then
        return nil
    end

    if #element.colspecs ~= 3 then
        return nil
    end

    local header_row = element.head.rows[1]
    if not header_row or #header_row.cells ~= 3 then
        return nil
    end

    local headers = {
        header_text(header_row.cells[1]),
        header_text(header_row.cells[2]),
        header_text(header_row.cells[3]),
    }

    if headers[1] ~= "Name of field" or headers[2] ~= "Mandatory" or headers[3] ~= "Description" then
        return nil
    end

    local widths = { 0.30, 0.15, 0.55 }
    for index, width in ipairs(widths) do
        element.colspecs[index][2] = width
    end

    return element
end