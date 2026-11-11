-- src/lua/endpoints/health.lua

-- ==========================================================================
-- Health Endpoint Params
-- ==========================================================================

---@class Request.Endpoint.Health.Params

-- ==========================================================================
-- Health Endpoint
-- ==========================================================================

---@type Endpoint
return {

  name = "health",

  description = "Health check endpoint for connection testing",

  schema = {},

  requires_state = nil,

  ---@param _ Request.Endpoint.Health.Params
  ---@param send_response fun(response: Response.Endpoint)
  execute = function(_, send_response)
    sendDebugMessage("health()", "BB.ENDPOINTS")
    sendDebugMessage("health() → ok", "BB.ENDPOINTS")
    send_response({
      status = "ok",
    })
  end,
}
