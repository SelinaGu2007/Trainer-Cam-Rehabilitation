#include "capture_source.h"

#include <k4arecord/playback.h>

#include <utility>

namespace {

class AzureKinectLiveSource final : public CaptureSource
{
public:
    explicit AzureKinectLiveSource(k4a_depth_mode_t depthMode)
        : m_depthMode(depthMode)
    {
    }

    ~AzureKinectLiveSource() override
    {
        Close();
    }

    bool Open(k4a_calibration_t& calibration, std::string& error) override
    {
        if (k4a_device_open(0, &m_device) != K4A_RESULT_SUCCEEDED)
        {
            error = "Unable to open Azure Kinect device 0";
            return false;
        }

        k4a_device_configuration_t configuration = K4A_DEVICE_CONFIG_INIT_DISABLE_ALL;
        configuration.depth_mode = m_depthMode;
        configuration.color_format = K4A_IMAGE_FORMAT_COLOR_BGRA32;
        configuration.color_resolution = K4A_COLOR_RESOLUTION_720P;
        if (k4a_device_start_cameras(m_device, &configuration) != K4A_RESULT_SUCCEEDED)
        {
            error = "Unable to start Azure Kinect cameras";
            Close();
            return false;
        }
        m_started = true;

        if (k4a_device_get_calibration(
                m_device, configuration.depth_mode, configuration.color_resolution, &calibration)
            != K4A_RESULT_SUCCEEDED)
        {
            error = "Unable to read Azure Kinect calibration";
            Close();
            return false;
        }
        return true;
    }

    CaptureReadStatus ReadCapture(k4a_capture_t* capture, int timeoutMs) override
    {
        const k4a_wait_result_t result = k4a_device_get_capture(m_device, capture, timeoutMs);
        if (result == K4A_WAIT_RESULT_SUCCEEDED)
        {
            return CaptureReadStatus::Success;
        }
        if (result == K4A_WAIT_RESULT_TIMEOUT)
        {
            return CaptureReadStatus::Timeout;
        }
        return CaptureReadStatus::Failed;
    }

    void Close() override
    {
        if (m_device != nullptr)
        {
            if (m_started)
            {
                k4a_device_stop_cameras(m_device);
            }
            k4a_device_close(m_device);
            m_device = nullptr;
            m_started = false;
        }
    }

    bool IsRealtime() const override { return true; }
    const char* DriverName() const override { return "azure-kinect-live"; }

private:
    k4a_depth_mode_t m_depthMode;
    k4a_device_t m_device = nullptr;
    bool m_started = false;
};

class AzureKinectRecordingSource final : public CaptureSource
{
public:
    explicit AzureKinectRecordingSource(std::string inputPath)
        : m_inputPath(std::move(inputPath))
    {
    }

    ~AzureKinectRecordingSource() override
    {
        Close();
    }

    bool Open(k4a_calibration_t& calibration, std::string& error) override
    {
        if (k4a_playback_open(m_inputPath.c_str(), &m_playback) != K4A_RESULT_SUCCEEDED)
        {
            error = "Unable to open Azure Kinect recording: " + m_inputPath;
            return false;
        }
        if (k4a_playback_get_calibration(m_playback, &calibration) != K4A_RESULT_SUCCEEDED)
        {
            error = "Unable to read calibration from Azure Kinect recording";
            Close();
            return false;
        }
        return true;
    }

    CaptureReadStatus ReadCapture(k4a_capture_t* capture, int /*timeoutMs*/) override
    {
        const k4a_stream_result_t result = k4a_playback_get_next_capture(m_playback, capture);
        if (result == K4A_STREAM_RESULT_SUCCEEDED)
        {
            return CaptureReadStatus::Success;
        }
        if (result == K4A_STREAM_RESULT_EOF)
        {
            return CaptureReadStatus::EndOfStream;
        }
        return CaptureReadStatus::Failed;
    }

    void Close() override
    {
        if (m_playback != nullptr)
        {
            k4a_playback_close(m_playback);
            m_playback = nullptr;
        }
    }

    bool IsRealtime() const override { return false; }
    const char* DriverName() const override { return "azure-kinect-recording"; }

private:
    std::string m_inputPath;
    k4a_playback_t m_playback = nullptr;
};

} // namespace

std::unique_ptr<CaptureSource> CreateCaptureSource(
    const std::string& driver,
    const std::string& inputPath,
    k4a_depth_mode_t depthMode,
    std::string& error)
{
    if (driver == "azure-kinect-live")
    {
        return std::make_unique<AzureKinectLiveSource>(depthMode);
    }
    if (driver == "azure-kinect-recording")
    {
        if (inputPath.empty())
        {
            error = "The azure-kinect-recording driver requires --input PATH";
            return nullptr;
        }
        return std::make_unique<AzureKinectRecordingSource>(inputPath);
    }

    error = "Unsupported capture driver: " + driver;
    return nullptr;
}
