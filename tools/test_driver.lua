local frameCount = 0
local outDir = "problems/"

function onInput()
    if frameCount == 1 then
        local inp = emu.getInput(0)
        emu.log("Input table keys:")
        for k, v in pairs(inp) do
            emu.log(k .. " = " .. tostring(v))
        end
    end

    -- Mash A, B, and Start to skip intro screens & advance text:
    -- Cycle: hold for 10 frames, release for 10 frames
    local pressA = (frameCount % 20) < 10
    local pressStart = (frameCount % 60) < 10
    emu.setInput({ a = pressA, b = pressA, start = pressStart }, 0)
end

function onEndFrame()
    frameCount = frameCount + 1

    -- Capture screenshots at regular intervals (every 120 frames / 2 seconds):
    if frameCount % 120 == 0 then
        local png = emu.takeScreenshot()
        local fname = string.format("%sauto_frame_%05d.png", outDir, frameCount)
        local f = io.open(fname, "wb")
        if f then
            f:write(png)
            f:close()
            emu.log("Saved screenshot: " .. fname)
        end
    end

    if frameCount >= 2400 then -- 40 seconds of emulation
        emu.log("Finished 2400 frames, stopping emulation.")
        emu.stop()
    end
end

emu.addEventCallback(onInput, emu.eventType.inputPolled)
emu.addEventCallback(onEndFrame, emu.eventType.endFrame)
emu.log("Driver script initialized successfully!")
