--[[
  HTTP Server - Single-client, non-blocking HTTP/1.1 server on port 12346.
  JSON-RPC 2.0 protocol over HTTP POST to "/" only.
]]

local socket = require("socket")
local json = require("json")

-- ============================================================================
-- Constants
-- ============================================================================

local MAX_BODY_SIZE = 65536 -- 64KB max request body
local RECV_CHUNK_SIZE = 8192 -- Read buffer size

-- ============================================================================
-- HTTP Parsing
-- ============================================================================

--- Parse HTTP request line (e.g., "POST / HTTP/1.1")
---@param line string
---@return table|nil request {method, path, version} or nil on error
local function parse_request_line(line)
  local method, path, version = line:match("^(%u+)%s+(%S+)%s+HTTP/(%d%.%d)")
  if not method then
    return nil
  end
  return { method = method, path = path, version = version }
end

--- Parse HTTP headers from header block
---@param header_lines string[] Array of header lines
---@return table headers {["header-name"] = "value", ...} (lowercase keys)
local function parse_headers(header_lines)
  local headers = {}
  for _, line in ipairs(header_lines) do
    local name, value = line:match("^([^:]+):%s*(.*)$")
    if name then
      headers[name:lower()] = value
    end
  end
  return headers
end

--- Format HTTP response with standard headers
---@param status_code number HTTP status code
---@param status_text string HTTP status text
---@param body string Response body
---@param extra_headers string[]|nil Additional headers
---@return string HTTP response
local function format_http_response(status_code, status_text, body, extra_headers)
  local headers = {
    "HTTP/1.1 " .. status_code .. " " .. status_text,
    "Content-Type: application/json",
    "Content-Length: " .. #body,
    "Connection: close",
  }

  -- Add any extra headers
  if extra_headers then
    for _, h in ipairs(extra_headers) do
      table.insert(headers, h)
    end
  end

  return table.concat(headers, "\r\n") .. "\r\n\r\n" .. body
end

-- ============================================================================
-- Server Module
-- ============================================================================

---@type Server
BB_SERVER = {
  host = BB_SETTINGS.host,
  port = BB_SETTINGS.port,
  server_socket = nil,
  client_socket = nil,
  current_request_id = nil,
  client_state = nil,
  openrpc_spec = nil,
  pending_response = false,  -- true while waiting for Event to send response
}

--- Create fresh client state for HTTP parsing
---@return table client_state
local function new_client_state()
  return {
    buffer = "",
  }
end

--- Initialize server socket and load OpenRPC spec
---@return boolean success
function BB_SERVER.init()
  -- Create and bind server socket
  local server, err = socket.tcp()
  if not server then
    sendErrorMessage("Failed to create socket: " .. tostring(err), "BB.SERVER")
    return false
  end

  -- Allow address reuse for faster restarts
  server:setoption("reuseaddr", true) ---@diagnostic disable-line: undefined-field

  local success, bind_err = server:bind(BB_SERVER.host, BB_SERVER.port)
  if not success then
    sendErrorMessage("Failed to bind to port " .. BB_SERVER.port .. ": " .. tostring(bind_err), "BB.SERVER")
    return false
  end

  local listen_success, listen_err = server:listen(1)
  if not listen_success then
    sendErrorMessage("Failed to listen: " .. tostring(listen_err), "BB.SERVER")
    server:close()
    return false
  end

  server:settimeout(0)
  BB_SERVER.server_socket = server

  -- Load OpenRPC spec file from mod directory
  local spec_path = SMODS.current_mod.path .. "src/lua/utils/openrpc.json"
  local spec_file = io.open(spec_path, "r")
  if spec_file then
    BB_SERVER.openrpc_spec = spec_file:read("*a")
    spec_file:close()
    sendDebugMessage("Loaded OpenRPC spec from " .. spec_path, "BB.SERVER")
  else
    sendWarnMessage("OpenRPC spec not found at " .. spec_path, "BB.SERVER")
    BB_SERVER.openrpc_spec = '{"error": "OpenRPC spec not found"}'
  end

  sendDebugMessage("HTTP server listening on http://" .. BB_SERVER.host .. ":" .. BB_SERVER.port, "BB.SERVER")
  return true
end

--- Accept new client connection
---@return boolean accepted
function BB_SERVER.accept()
  if not BB_SERVER.server_socket then
    return false
  end

  local client, err = BB_SERVER.server_socket:accept()
  if err then
    if err ~= "timeout" then
      sendErrorMessage("Failed to accept client: " .. tostring(err), "BB.SERVER")
    end
    return false
  end

  if client then
    -- If we're waiting for an Event to send a response, reject the new
    -- connection to protect the pending socket.
    if BB_SERVER.pending_response and BB_SERVER.client_socket then
      -- Send a quick "busy" response before closing so the client
      -- gets a clean HTTP error instead of a TCP abort.
      local busy_body = '{"jsonrpc":"2.0","error":{"code":-32002,"message":"Server busy (pending response)","data":{"name":"INVALID_STATE"}},"id":null}'
      local busy_resp = format_http_response(503, "Service Unavailable", busy_body)
      client:settimeout(1)
      client:send(busy_resp)
      client:close()
      sendDebugMessage("Client rejected with 503 (pending response)", "BB.SERVER")
      return false
    end

    -- Close existing client if any
    if BB_SERVER.client_socket then
      BB_SERVER.client_socket:close()
      BB_SERVER.client_socket = nil
      BB_SERVER.client_state = nil
    end

    client:settimeout(0)
    BB_SERVER.client_socket = client
    BB_SERVER.client_state = new_client_state()
    sendDebugMessage("Client connected", "BB.SERVER")
    return true
  end

  return false
end

--- Close current client connection
local function close_client()
  if BB_SERVER.client_socket then
    BB_SERVER.client_socket:close()
    BB_SERVER.client_socket = nil
    BB_SERVER.client_state = nil
  end
end

--- Try to parse a complete HTTP request from the buffer
---@return table|nil request Parsed request or nil if incomplete
local function try_parse_http()
  local state = BB_SERVER.client_state
  if not state then
    return nil
  end

  local buffer = state.buffer

  -- Find end of headers (double CRLF)
  local header_end = buffer:find("\r\n\r\n")
  if not header_end then
    return nil -- Incomplete, wait for more data
  end

  -- Split header section into lines
  local header_section = buffer:sub(1, header_end - 1)
  local lines = {}
  for line in header_section:gmatch("[^\r\n]+") do
    table.insert(lines, line)
  end

  if #lines == 0 then
    return { error = "Empty request" }
  end

  -- Parse request line
  local request = parse_request_line(lines[1])
  if not request then
    return { error = "Invalid request line" }
  end

  -- Parse headers
  local header_lines = {}
  for i = 2, #lines do
    table.insert(header_lines, lines[i])
  end
  request.headers = parse_headers(header_lines)

  -- Handle body for POST requests
  local body_start = header_end + 4
  if request.method == "POST" then
    local content_length = tonumber(request.headers["content-length"] or 0)

    -- Validate content length
    if content_length > MAX_BODY_SIZE then
      return { error = "Request body too large" }
    end

    -- Check if we have the complete body
    local body_available = #buffer - body_start + 1
    if body_available < content_length then
      return nil -- Incomplete body, wait for more data
    end

    request.body = buffer:sub(body_start, body_start + content_length - 1)
  else
    request.body = ""
  end

  return request
end

--- Send raw HTTP response to client
---@param response_str string Complete HTTP response
---@return boolean success
local function send_raw(response_str)
  if not BB_SERVER.client_socket then
    return false
  end

  local _, err = BB_SERVER.client_socket:send(response_str)
  if err then
    sendDebugMessage("Failed to send response: " .. err, "BB.SERVER")
    return false
  end
  return true
end

--- Send HTTP error response
---@param status_code number HTTP status code
---@param message string Error message
local function send_http_error(status_code, message)
  BB_SERVER.pending_response = false
  local status_texts = {
    [400] = "Bad Request",
    [404] = "Not Found",
    [405] = "Method Not Allowed",
    [500] = "Internal Server Error",
  }

  local status_text = status_texts[status_code] or "Error"
  local error_name = status_code == 500 and BB_ERROR_NAMES.INTERNAL_ERROR or BB_ERROR_NAMES.BAD_REQUEST

  local body = json.encode({
    jsonrpc = "2.0",
    error = {
      code = BB_ERROR_CODES[error_name],
      message = message,
      data = { name = error_name },
    },
    id = BB_SERVER.current_request_id,
  })

  send_raw(format_http_response(status_code, status_text, body))
  close_client()
end

--- Handle JSON-RPC request
---@param body string Request body (JSON)
---@param dispatcher Dispatcher
local function handle_jsonrpc(body, dispatcher)
  -- Validate JSON
  local success, parsed = pcall(json.decode, body)
  if not success or type(parsed) ~= "table" then
    BB_SERVER.current_request_id = nil
    BB_SERVER.send_response({
      message = "Invalid JSON in request body",
      name = BB_ERROR_NAMES.BAD_REQUEST,
    })
    return
  end

  -- Validate JSON-RPC version
  if parsed.jsonrpc ~= "2.0" then
    BB_SERVER.current_request_id = parsed.id
    BB_SERVER.send_response({
      message = "Invalid JSON-RPC version: expected '2.0'",
      name = BB_ERROR_NAMES.BAD_REQUEST,
    })
    return
  end

  -- Validate request ID (must be non-null integer or string)
  if parsed.id == nil then
    BB_SERVER.current_request_id = nil
    BB_SERVER.send_response({
      message = "Invalid Request: 'id' field is required",
      name = BB_ERROR_NAMES.BAD_REQUEST,
    })
    return
  end

  local id_type = type(parsed.id)
  if id_type ~= "number" and id_type ~= "string" then
    BB_SERVER.current_request_id = nil
    BB_SERVER.send_response({
      message = "Invalid Request: 'id' must be an integer or string",
      name = BB_ERROR_NAMES.BAD_REQUEST,
    })
    return
  end

  if id_type == "number" and parsed.id ~= math.floor(parsed.id) then
    BB_SERVER.current_request_id = nil
    BB_SERVER.send_response({
      message = "Invalid Request: 'id' must be an integer, not a float",
      name = BB_ERROR_NAMES.BAD_REQUEST,
    })
    return
  end

  BB_SERVER.current_request_id = parsed.id
  BB_SERVER.pending_response = true

  -- Dispatch to endpoint
  if dispatcher and dispatcher.dispatch then
    dispatcher.dispatch(parsed)
  else
    BB_SERVER.send_response({
      message = "Server not fully initialized (dispatcher not ready)",
      name = BB_ERROR_NAMES.INVALID_STATE,
    })
  end
end

--- Handle parsed HTTP request
---@param request table Parsed HTTP request
---@param dispatcher Dispatcher
local function handle_http_request(request, dispatcher)
  -- Handle parse errors
  if request.error then
    send_http_error(400, request.error)
    return
  end

  local method = request.method
  local path = request.path

  -- Only POST method is allowed
  if method ~= "POST" then
    send_http_error(405, "Method not allowed. Use POST for JSON-RPC requests")
    return
  end

  -- Only root path is allowed
  if path ~= "/" then
    send_http_error(404, "Not found. Use POST to '/' for JSON-RPC requests")
    return
  end

  handle_jsonrpc(request.body, dispatcher)
end

--- Send JSON-RPC response to client (called by endpoints)
---@param response Response.Endpoint
---@return boolean success
function BB_SERVER.send_response(response)
  BB_SERVER.pending_response = false
  if not BB_SERVER.client_socket then
    return false
  end

  local wrapped
  if response.message then
    -- Error response
    local error_name = response.name or BB_ERROR_NAMES.INTERNAL_ERROR
    local error_code = BB_ERROR_CODES[error_name] or BB_ERROR_CODES.INTERNAL_ERROR
    wrapped = {
      jsonrpc = "2.0",
      error = {
        code = error_code,
        message = response.message,
        data = { name = error_name },
      },
      id = BB_SERVER.current_request_id,
    }
  else
    -- Success response
    wrapped = {
      jsonrpc = "2.0",
      result = response,
      id = BB_SERVER.current_request_id,
    }
  end

  local success, json_str = pcall(json.encode, wrapped)
  if not success then
    sendDebugMessage("Failed to encode response: " .. tostring(json_str), "BB.SERVER")
    return false
  end

  -- Send HTTP response
  local http_response = format_http_response(200, "OK", json_str)
  local sent = send_raw(http_response)

  -- Close connection after response (Connection: close)
  close_client()

  return sent
end

--- Main update loop - called each frame
---@param dispatcher Dispatcher
function BB_SERVER.update(dispatcher)
  if not BB_SERVER.server_socket then
    return
  end

  -- Try to accept new connections
  BB_SERVER.accept()

  -- Handle existing client
  if BB_SERVER.client_socket and BB_SERVER.client_state then
    -- Read available data into buffer (non-blocking)
    BB_SERVER.client_socket:settimeout(0)
    local chunk, err, partial = BB_SERVER.client_socket:receive(RECV_CHUNK_SIZE)
    local data = chunk or partial

    if data and #data > 0 then
      BB_SERVER.client_state.buffer = BB_SERVER.client_state.buffer .. data

      -- Try to parse complete HTTP request
      local request = try_parse_http()
      if request then
        handle_http_request(request, dispatcher)
      end
    elseif err == "closed" then
      close_client()
    end
  end
end

--- Close server and all connections
function BB_SERVER.close()
  close_client()

  if BB_SERVER.server_socket then
    BB_SERVER.server_socket:close()
    BB_SERVER.server_socket = nil
    sendDebugMessage("Server closed", "BB.SERVER")
  end
end
