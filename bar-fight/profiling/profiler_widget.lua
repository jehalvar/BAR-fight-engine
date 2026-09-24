-- Diagnostic only: unchanged production collector and checksum observer run separately.
function widget:GetInfo()
  return {name="Replay Fork Profiler", desc="Raw optimized-engine profiler snapshots",
    author="BAR Fight diagnostic", layer=99999999999, enabled=true}
end
if not (Platform and Platform.isHeadless) or not Spring.IsReplay() then return false end
local output, baseline, gameOverFrame, closed = nil, false, nil, false
local function quote(value)
  return '"' .. tostring(value):gsub('[%z\1-\31\\"]', function(c)
    if c == '"' then return '\\"' elseif c == '\\' then return '\\\\' end
    return string.format('\\u%04x', string.byte(c))
  end) .. '"'
end
local function snapshot(phase)
  local names=Spring.GetProfilerRecordNames()
  table.sort(names)
  output:write(string.format('{"kind":"snapshot","phase":%s,"frame":%d,"names":%d}\n',
    quote(phase),Spring.GetGameFrame(),#names))
  for _,name in ipairs(names) do
    local total,current,maxDt,pct,peak=Spring.GetProfilerTimeRecord(name,false)
    assert(type(total)=="number" and total==total and total>=0, "Invalid profiler total")
    output:write(string.format('{"kind":"record","phase":%s,"name":%s,"total_ms":%.17g,"current_ms":%.17g,"max_dt_ms":%.17g,"time_fraction":%.17g,"peak_fraction":%.17g}\n',
      quote(phase),quote(name),total,current,maxDt,pct,peak))
  end
  output:flush()
end
function widget:Initialize()
  output=assert(io.open("LuaUI/fork-profiler.jsonl","w"))
  output:write('{"kind":"meta","schema":2,"initial_frame":'..Spring.GetGameFrame()
    ..',"engine":'..quote(Engine.version)..',"engine_full":'..quote(Engine.versionFull)
    ..',"options":'..Spring.GetConfigInt("ReplayPerformanceOptions",0)
    ..',"diagnostic_not_timing_ab":true,"command":"debug 1 0"}\n')
  output:flush()
  Spring.SendCommands("debug 1 0")
end
function widget:GameFrame(frame)
  if frame==0 and not baseline then snapshot("frame0"); baseline=true end
end
function widget:GameOver()
  gameOverFrame=Spring.GetGameFrame()
  snapshot("game_over")
end
function widget:Shutdown()
  if closed or not output then return end
  snapshot("shutdown")
  output:write(string.format('{"kind":"end","baseline_frame0":%s,"game_over_frame":%d,"last_frame":%d}\n',
    tostring(baseline),gameOverFrame or -1,Spring.GetGameFrame()))
  output:flush(); output:close(); closed=true
end
