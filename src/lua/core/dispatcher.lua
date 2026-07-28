--[[
  Request Dispatcher - Routes API requests to endpoints with 4-tier validation:
  1. Protocol (method field)  2. Schema (via Validator)
  3. Game state               4. Execution
]]

---@type Validator
local Validator = assert(SMODS.load_file("src/lua/core/validator.lua"))()
---@type BB_FORMAT
local BB_FORMAT = assert(SMODS.load_file("src/lua/utils/format.lua"))()
local socket = require("socket")

---@type table<integer, string>?
local STATE_NAME_CACHE = nil

---@param state_value integer|string
---@return string
local function get_state_name(state_value)
  if not STATE_NAME_CACHE then
    STATE_NAME_CACHE = {}
    if G and G.STATES then
      for name, value in pairs(G.STATES) do
        STATE_NAME_CACHE[value] = name
      end
    end
  end
  return STATE_NAME_CACHE[state_value] or tostring(state_value)
end

---@type Dispatcher
BB_DISPATCHER = {
  endpoints = {},
  Server = nil,
}

---@param endpoint Endpoint
---@return boolean success
---@return string? error_message
local function validate_endpoint_structure(endpoint)
  if not endpoint.name or type(endpoint.name) ~= "string" then
    return false, "Endpoint missing 'name' field (string)"
  end
  if not endpoint.description or type(endpoint.description) ~= "string" then
    return false, "Endpoint '" .. endpoint.name .. "' missing 'description' field (string)"
  end
  if not endpoint.schema or type(endpoint.schema) ~= "table" then
    return false, "Endpoint '" .. endpoint.name .. "' missing 'schema' field (table)"
  end
  if not endpoint.execute or type(endpoint.execute) ~= "function" then
    return false, "Endpoint '" .. endpoint.name .. "' missing 'execute' field (function)"
  end
  if endpoint.requires_state ~= nil and type(endpoint.requires_state) ~= "table" then
    return false, "Endpoint '" .. endpoint.name .. "' 'requires_state' must be nil or table"
  end
  for field_name, field_schema in pairs(endpoint.schema) do
    if type(field_schema) ~= "table" then
      return false, "Endpoint '" .. endpoint.name .. "' schema field '" .. field_name .. "' must be a table"
    end
    if not field_schema.type then
      return false, "Endpoint '" .. endpoint.name .. "' schema field '" .. field_name .. "' missing 'type' definition"
    end
  end
  return true
end

---@param endpoint Endpoint
---@return boolean success
---@return string? error_message
function BB_DISPATCHER.register(endpoint)
  local valid, err = validate_endpoint_structure(endpoint)
  if not valid then
    return false, err
  end
  if BB_DISPATCHER.endpoints[endpoint.name] then
    return false, "Endpoint '" .. endpoint.name .. "' is already registered"
  end
  BB_DISPATCHER.endpoints[endpoint.name] = endpoint
  sendDebugMessage("Registered endpoint: " .. endpoint.name, "BB.DISPATCHER")
  return true
end

---@param endpoint_files string[]
---@return boolean success
---@return string? error_message
function BB_DISPATCHER.load_endpoints(endpoint_files)
  local loaded_count = 0
  for _, filepath in ipairs(endpoint_files) do
    sendDebugMessage("Loading endpoint: " .. filepath, "BB.DISPATCHER")
    local success, endpoint = pcall(function()
      return assert(SMODS.load_file(filepath))()
    end)
    if not success then
      return false, "Failed to load endpoint '" .. filepath .. "': " .. tostring(endpoint)
    end
    local reg_success, reg_err = BB_DISPATCHER.register(endpoint)
    if not reg_success then
      return false, "Failed to register endpoint '" .. filepath .. "': " .. reg_err
    end
    loaded_count = loaded_count + 1
  end
  sendInfoMessage("Loaded " .. loaded_count .. " endpoint(s)", "BB.DISPATCHER")
  return true
end

---@param server_module table
---@param endpoint_files string[]?
---@return boolean success
function BB_DISPATCHER.init(server_module, endpoint_files)
  BB_DISPATCHER.Server = server_module
  endpoint_files = endpoint_files or { "src/lua/endpoints/health.lua" }
  local success, err = BB_DISPATCHER.load_endpoints(endpoint_files)
  if not success then
    sendErrorMessage("Dispatcher initialization failed: " .. err, "BB.DISPATCHER")
    return false
  end
  sendInfoMessage("Dispatcher initialized", "BB.DISPATCHER")
  return true
end

---@param message string
---@param error_code string
function BB_DISPATCHER.send_error(message, error_code)
  if not BB_DISPATCHER.Server then
    sendErrorMessage("Cannot send error - Server not initialized", "BB.DISPATCHER")
    return
  end
  BB_DISPATCHER.Server.send_response({
    message = message,
    name = error_code,
  })
end

---@param request Request.Server
function BB_DISPATCHER.dispatch(request)
  -- Trigger render for this frame if ondemand mode is enabled
  if BB_RENDER ~= nil then
    BB_RENDER = true
  end

  -- TIER 1: Protocol Validation (jsonrpc version checked in server.receive())
  if not request.method or type(request.method) ~= "string" then
    BB_DISPATCHER.send_error("Request missing 'method' field", BB_ERROR_NAMES.BAD_REQUEST)
    return
  end

  -- Handle rpc.discover (OpenRPC Service Discovery)
  if request.method == "rpc.discover" then
    if BB_DISPATCHER.Server and BB_DISPATCHER.Server.openrpc_spec then
      local json = require("json")
      local success, spec = pcall(json.decode, BB_DISPATCHER.Server.openrpc_spec)
      if success then
        BB_DISPATCHER.Server.send_response(spec)
      else
        BB_DISPATCHER.send_error("Failed to parse OpenRPC spec", BB_ERROR_NAMES.INTERNAL_ERROR)
      end
    else
      BB_DISPATCHER.send_error("OpenRPC spec not available", BB_ERROR_NAMES.INTERNAL_ERROR)
    end
    return
  end

  local params = request.params or {}
  local endpoint = BB_DISPATCHER.endpoints[request.method]
  if not endpoint then
    BB_DISPATCHER.send_error("Unknown method: " .. request.method, BB_ERROR_NAMES.BAD_REQUEST)
    return
  end

  -- Log incoming request with params
  local start_time = socket.gettime()
  sendDebugMessage(request.method .. BB_FORMAT.serialize_params(params), "BB.REQUEST")

  -- TIER 2: Schema Validation
  local valid, err_msg, err_code = Validator.validate(params, endpoint.schema)
  if not valid then
    sendWarnMessage(request.method .. ": " .. (err_msg or "Validation failed"), "BB.VALIDATION")
    BB_DISPATCHER.send_error(err_msg or "Validation failed", err_code or BB_ERROR_NAMES.BAD_REQUEST)
    return
  end

  -- TIER 3: Game State Validation
  if endpoint.requires_state then
    local current_state = G and G.STATE or "UNKNOWN"
    local state_valid = false
    for _, required_state in ipairs(endpoint.requires_state) do
      if current_state == required_state then
        state_valid = true
        break
      end
    end
    if not state_valid then
      local state_names = {}
      for _, state in ipairs(endpoint.requires_state) do
        table.insert(state_names, get_state_name(state))
      end
      local current_state_name = get_state_name(current_state)
      sendWarnMessage(
        string.format("%s: requires %s, current=%s", request.method, table.concat(state_names, "|"), current_state_name),
        "BB.STATE"
      )
      BB_DISPATCHER.send_error(
        "Method '" .. request.method .. "' requires one of these states: " .. table.concat(state_names, ", "),
        BB_ERROR_NAMES.INVALID_STATE
      )
      return
    end
  end

  -- TIER 4: Execute Endpoint
  local function send_response(response)
    if BB_DISPATCHER.Server then
      -- Log response with timing
      local duration_ms = (socket.gettime() - start_time) * 1000
      local is_error = response.message ~= nil
      if is_error then
        sendWarnMessage(string.format("%s ERR (%.0fms)", request.method, duration_ms), "BB.RESPONSE")
      else
        sendInfoMessage(string.format("%s OK (%.0fms)", request.method, duration_ms), "BB.RESPONSE")
      end
      BB_DISPATCHER.Server.send_response(response)
    else
      sendErrorMessage("Cannot send response - Server not initialized", "BB.DISPATCHER")
    end
  end
  local exec_success, exec_error = pcall(function()
    endpoint.execute(params, send_response)
  end)
  if not exec_success then
    sendErrorMessage(request.method .. ": " .. tostring(exec_error), "BB.EXEC")
    BB_DISPATCHER.send_error(tostring(exec_error), BB_ERROR_NAMES.INTERNAL_ERROR)
  end
end
