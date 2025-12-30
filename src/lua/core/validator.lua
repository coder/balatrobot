--[[
  Schema Validator - Fail-fast validation for endpoint arguments.
  Types: string, integer, boolean, array, table.
  No defaults or range validation (endpoints handle these).
]]

local Validator = {}

---@param value any
---@return boolean
local function is_integer(value)
  return type(value) == "number" and math.floor(value) == value
end

---@param value any
---@return boolean
local function is_array(value)
  if type(value) ~= "table" then
    return false
  end
  local count = 0
  for k, _ in pairs(value) do
    count = count + 1
    if type(k) ~= "number" or k ~= count then
      return false
    end
  end
  return true
end

---@param field_name string
---@param value any
---@param field_schema Endpoint.Schema
---@return boolean success
---@return string? error_message
---@return string? error_code
local function validate_field(field_name, value, field_schema)
  local expected_type = field_schema.type
  if expected_type == "integer" then
    if not is_integer(value) then
      return false, "Field '" .. field_name .. "' must be an integer", BB_ERROR_NAMES.BAD_REQUEST
    end
  elseif expected_type == "array" then
    if not is_array(value) then
      return false, "Field '" .. field_name .. "' must be an array", BB_ERROR_NAMES.BAD_REQUEST
    end
  elseif expected_type == "table" then
    if type(value) ~= "table" or (next(value) ~= nil and is_array(value)) then
      return false, "Field '" .. field_name .. "' must be a table", BB_ERROR_NAMES.BAD_REQUEST
    end
  else
    if type(value) ~= expected_type then
      return false, "Field '" .. field_name .. "' must be of type " .. expected_type, BB_ERROR_NAMES.BAD_REQUEST
    end
  end
  if expected_type == "array" and field_schema.items then
    for i, item in ipairs(value) do
      local item_type = field_schema.items
      local item_valid = item_type == "integer" and is_integer(item) or type(item) == item_type
      if not item_valid then
        return false,
          "Field '" .. field_name .. "' array item at index " .. (i - 1) .. " must be of type " .. item_type,
          BB_ERROR_NAMES.BAD_REQUEST
      end
    end
  end
  return true
end

---@param args table
---@param schema table<string, Endpoint.Schema>
---@return boolean success
---@return string? error_message
---@return string? error_code
function Validator.validate(args, schema)
  if type(args) ~= "table" then
    return false, "Arguments must be a table", BB_ERROR_NAMES.BAD_REQUEST
  end
  for field_name, field_schema in pairs(schema) do
    local value = args[field_name]
    if field_schema.required and value == nil then
      return false, "Missing required field '" .. field_name .. "'", BB_ERROR_NAMES.BAD_REQUEST
    end
    if value ~= nil then
      local success, err_msg, err_code = validate_field(field_name, value, field_schema)
      if not success then
        return false, err_msg, err_code
      end
    end
  end
  return true
end

return Validator
