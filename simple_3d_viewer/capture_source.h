#pragma once

#include <k4a/k4a.h>

#include <memory>
#include <string>

enum class CaptureReadStatus
{
    Success,
    Timeout,
    EndOfStream,
    Failed
};

class CaptureSource
{
public:
    virtual ~CaptureSource() = default;

    virtual bool Open(k4a_calibration_t& calibration, std::string& error) = 0;
    virtual CaptureReadStatus ReadCapture(k4a_capture_t* capture, int timeoutMs) = 0;
    virtual void Close() = 0;
    virtual bool IsRealtime() const = 0;
    virtual const char* DriverName() const = 0;
};

std::unique_ptr<CaptureSource> CreateCaptureSource(
    const std::string& driver,
    const std::string& inputPath,
    k4a_depth_mode_t depthMode,
    std::string& error);
