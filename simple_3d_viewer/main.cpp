// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#include <array>
#include <iostream>
#include <map>
#include <memory>
#include <vector>
#include <k4a/k4a.h>
#include <k4abt.h>

#include "capture_source.h"

#include <BodyTrackingHelpers.h>
#include <Utilities.h>
#include <Window3dWrapper.h>
#include <fstream>

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream> 
#include <opencv2/opencv.hpp>
#include <filesystem>

std::tm ToLocalTime(std::time_t value)
{
    std::tm localTime{};
#ifdef _WIN32
    localtime_s(&localTime, &value);
#else
    localtime_r(&value, &localTime);
#endif
    return localTime;
}

std::tm ToUtcTime(std::time_t value)
{
    std::tm utcTime{};
#ifdef _WIN32
    gmtime_s(&utcTime, &value);
#else
    gmtime_r(&value, &utcTime);
#endif
    return utcTime;
}


void PrintUsage()
{
    printf("\nOUTPUT_FOLDER is required as the first argument.\n");
#ifdef _WIN32
    printf("\nUSAGE: simple_3d_viewer.exe OUTPUT_FOLDER [--source azure-kinect-live|azure-kinect-recording] [--input FILE.mkv] [--depth-mode NFOV_UNBINNED|WFOV_BINNED] [--processing-mode CPU|CUDA|DIRECTML|TENSORRT] [--model MODEL_PATH]\n");
#else
    printf("\nUSAGE: simple_3d_viewer OUTPUT_FOLDER [--source azure-kinect-live|azure-kinect-recording] [--input FILE.mkv] [--depth-mode NFOV_UNBINNED|WFOV_BINNED] [--processing-mode CPU|CUDA|TENSORRT] [--model MODEL_PATH]\n");
#endif
    printf("  - SensorMode: \n");
    printf("      NFOV_UNBINNED (default) - Narrow Field of View Unbinned Mode [Resolution: 640x576; FOI: 75 degree x 65 degree]\n");
    printf("      WFOV_BINNED             - Wide Field of View Binned Mode [Resolution: 512x512; FOI: 120 degree x 120 degree]\n");
    printf("  - RuntimeMode: \n");
    printf("      CPU - Use the CPU only mode. It runs on machines without a GPU but it will be much slower\n");
    printf("      CUDA - Use CUDA for processing.\n");
#ifdef _WIN32
    printf("      DIRECTML - Use the DirectML processing mode.\n");
#endif
    printf("      TENSORRT - Use the TensorRT processing mode.\n");
    printf("  - Capture source:\n");
    printf("      azure-kinect-live      - Read from Azure Kinect device 0 (default)\n");
    printf("      azure-kinect-recording - Read a recorded Azure Kinect MKV supplied with --input\n");
    printf("e.g.   (k4abt_)simple_3d_viewer.exe C:\\recordings\\session1 WFOV_BINNED CPU\n");
    printf("e.g.   (k4abt_)simple_3d_viewer.exe C:\\recordings\\session1 CPU\n");
    printf("e.g.   (k4abt_)simple_3d_viewer.exe C:\\recordings\\session1 WFOV_BINNED\n");
    printf("e.g.   simple_3d_viewer.exe C:\\recordings\\session1 --source azure-kinect-recording --input MyFile.mkv --processing-mode CPU\n");
    printf("Legacy positional sensor/runtime arguments and OFFLINE MyFile.mkv remain supported.\n");
}

void PrintAppUsage()
{
    printf("\n");
    printf(" Basic Navigation:\n\n");
    printf(" Rotate: Rotate the camera by moving the mouse while holding mouse left button\n");
    printf(" Pan: Translate the scene by holding Ctrl key and drag the scene with mouse left button\n");
    printf(" Zoom in/out: Move closer/farther away from the scene center by scrolling the mouse scroll wheel\n");
    printf(" Select Center: Center the scene based on a detected joint by right clicking the joint with mouse\n");
    printf("\n");
    printf(" Key Shortcuts\n\n");
    printf(" ESC: quit\n");
    printf(" h: help\n");
    printf(" b: body visualization mode\n");
    printf(" k: 3d window layout\n");
    printf("\n");
}

// Global State and Key Process Function
bool s_isRunning = true;
Visualization::Layout3d s_layoutMode = Visualization::Layout3d::OnlyMainView;
bool s_visualizeJointFrame = false;


int64_t ProcessKey(void* /*context*/, int key)
{
    // https://www.glfw.org/docs/latest/group__keys.html
    switch (key)
    {
        // Quit
    case GLFW_KEY_ESCAPE:
        s_isRunning = false;
        break;
    case GLFW_KEY_K:
        s_layoutMode = (Visualization::Layout3d)(((int)s_layoutMode + 1) % (int)Visualization::Layout3d::Count);
        break;
    case GLFW_KEY_B:
        s_visualizeJointFrame = !s_visualizeJointFrame;
        break;
    case GLFW_KEY_H:
        PrintAppUsage();
        break;
    }
    return 1;
}

int64_t CloseCallback(void* /*context*/)
{
    s_isRunning = false;
    return 1;
}

struct InputSettings
{
    k4a_depth_mode_t DepthCameraMode = K4A_DEPTH_MODE_NFOV_UNBINNED;
#ifdef _WIN32
    k4abt_tracker_processing_mode_t processingMode = K4ABT_TRACKER_PROCESSING_MODE_GPU_DIRECTML;
#else
    k4abt_tracker_processing_mode_t processingMode = K4ABT_TRACKER_PROCESSING_MODE_GPU_CUDA;
#endif
    std::string SourceDriver = "azure-kinect-live";
    std::string InputPath;
    std::string ModelPath;
};

bool ApplyDepthMode(const std::string& value, InputSettings& settings)
{
    if (value == "NFOV_UNBINNED")
    {
        settings.DepthCameraMode = K4A_DEPTH_MODE_NFOV_UNBINNED;
        return true;
    }
    if (value == "WFOV_BINNED")
    {
        settings.DepthCameraMode = K4A_DEPTH_MODE_WFOV_2X2BINNED;
        return true;
    }
    return false;
}

bool ApplyProcessingMode(const std::string& value, InputSettings& settings)
{
    if (value == "CPU")
    {
        settings.processingMode = K4ABT_TRACKER_PROCESSING_MODE_CPU;
        return true;
    }
    if (value == "TENSORRT")
    {
        settings.processingMode = K4ABT_TRACKER_PROCESSING_MODE_GPU_TENSORRT;
        return true;
    }
    if (value == "CUDA")
    {
        settings.processingMode = K4ABT_TRACKER_PROCESSING_MODE_GPU_CUDA;
        return true;
    }
#ifdef _WIN32
    if (value == "DIRECTML")
    {
        settings.processingMode = K4ABT_TRACKER_PROCESSING_MODE_GPU_DIRECTML;
        return true;
    }
#endif
    return false;
}

bool ParseInputSettingsFromArg(int argc, char** argv, InputSettings& inputSettings)
{
    // argv[1] is the recording output directory.
    for (int i = 2; i < argc; i++)
    {
        std::string inputArg(argv[i]);
        if (inputArg == "--source")
        {
            if (i >= argc - 1)
            {
                printf("Error: capture source missing\n");
                return false;
            }
            inputSettings.SourceDriver = argv[++i];
        }
        else if (inputArg == "--input")
        {
            if (i >= argc - 1)
            {
                printf("Error: input path missing\n");
                return false;
            }
            inputSettings.InputPath = argv[++i];
        }
        else if (inputArg == "--depth-mode")
        {
            if (i >= argc - 1 || !ApplyDepthMode(argv[++i], inputSettings))
            {
                printf("Error: invalid depth mode\n");
                return false;
            }
        }
        else if (inputArg == "--processing-mode")
        {
            if (i >= argc - 1 || !ApplyProcessingMode(argv[++i], inputSettings))
            {
                printf("Error: invalid processing mode\n");
                return false;
            }
        }
        else if (ApplyDepthMode(inputArg, inputSettings))
        {
            // Legacy positional depth mode.
        }
        else if (ApplyProcessingMode(inputArg, inputSettings))
        {
            // Legacy positional processing mode.
        }
        else if (inputArg == "OFFLINE")
        {
            inputSettings.SourceDriver = "azure-kinect-recording";
            if (i < argc - 1) {
                inputSettings.InputPath = argv[i + 1];
                i++;
            }
            else {
                return false;
            }
        }
        else if (inputArg == "-model" || inputArg == "--model")
        {
            if (i < argc - 1)
                inputSettings.ModelPath = argv[++i];
            else
            {
                printf("Error: model path missing\n");
                return false;
            }
        }
        else
        {
            printf("Error: command not understood: %s\n", inputArg.c_str());
            return false;
        }
    }
    if (inputSettings.SourceDriver != "azure-kinect-live"
        && inputSettings.SourceDriver != "azure-kinect-recording")
    {
        printf("Error: unsupported capture source: %s\n", inputSettings.SourceDriver.c_str());
        return false;
    }
    if (inputSettings.SourceDriver == "azure-kinect-recording" && inputSettings.InputPath.empty())
    {
        printf("Error: azure-kinect-recording requires --input PATH\n");
        return false;
    }
    return true;
}



void print_body_information(k4abt_body_t body, std::ofstream& outputFile)
{
    std::cout << "Body ID: " << body.id << std::endl;
    outputFile << "Body ID: " << body.id << std::endl;

    for (int i = 0; i < (int)K4ABT_JOINT_COUNT; i++)
    {
        k4a_float3_t position = body.skeleton.joints[i].position;
        k4a_quaternion_t orientation = body.skeleton.joints[i].orientation;
        k4abt_joint_confidence_level_t confidence_level = body.skeleton.joints[i].confidence_level;
        outputFile << "Joint[" << i << "]: Position[] ( " << position.v[0] << ", " << position.v[1] << ", " << position.v[2] << " ); Orientation ( "
            << orientation.v[0] << ", " << orientation.v[1] << ", " << orientation.v[2] << ", " << orientation.v[3] << "); Confidence Level ("
            << confidence_level << ")" << std::endl;
        printf("Joint[%d]: Position[mm] ( %f, %f, %f ); Orientation ( %f, %f, %f, %f); Confidence Level (%d)  \n",
            i, position.v[0], position.v[1], position.v[2], orientation.v[0], orientation.v[1], orientation.v[2], orientation.v[3], confidence_level);
    }
}

void write_body_json(k4abt_body_t body, std::ofstream& motionFramesFile)
{
    motionFramesFile << "{\"body_id\":" << body.id << ",\"joints\":[";
    for (int i = 0; i < static_cast<int>(K4ABT_JOINT_COUNT); ++i)
    {
        if (i > 0)
        {
            motionFramesFile << ',';
        }
        const k4abt_joint_t& joint = body.skeleton.joints[i];
        motionFramesFile << "{\"joint_index\":" << i
            << ",\"position_mm\":[" << joint.position.v[0] << ',' << joint.position.v[1] << ',' << joint.position.v[2] << ']'
            << ",\"orientation_wxyz\":[" << joint.orientation.v[0] << ',' << joint.orientation.v[1] << ','
            << joint.orientation.v[2] << ',' << joint.orientation.v[3] << ']'
            << ",\"confidence_level\":" << static_cast<int>(joint.confidence_level) << '}';
    }
    motionFramesFile << "]}";
}

bool save_color_image(k4a_capture_t capture, int idx, const std::string& folderPath) {
    if (capture == nullptr)
    {
        return false;
    }
    k4a_image_t color_image = k4a_capture_get_color_image(capture);

    if (color_image != NULL) {
        int width = k4a_image_get_width_pixels(color_image);
        int height = k4a_image_get_height_pixels(color_image);
        cv::Mat colorMat(cv::Size(width, height), CV_8UC4, k4a_image_get_buffer(color_image));
        
        // Save frame image with both legacy (typo) and corrected filename for backward compatibility
        const std::string legacy_path = folderPath + "\\imamge_idx_" + std::to_string(idx) + ".jpg";
        const std::string fixed_path  = folderPath + "\\image_idx_"  + std::to_string(idx) + ".jpg";
        const bool legacySaved = cv::imwrite(legacy_path, colorMat);
        const bool fixedSaved = cv::imwrite(fixed_path, colorMat);

        k4a_image_release(color_image);
        return legacySaved && fixedSaved;
    }
    return false;
}








void VisualizeResult(k4abt_frame_t bodyFrame, Window3dWrapper& window3d, int depthWidth, int depthHeight,
    std::ofstream& outputFile, std::ofstream& motionFramesFile, int idx, const std::string& folderPath) {

    // Obtain original capture that generates the body tracking result
    k4a_capture_t originalCapture = k4abt_frame_get_capture(bodyFrame);
    k4a_image_t depthImage = k4a_capture_get_depth_image(originalCapture);

    std::vector<Color> pointCloudColors(depthWidth * depthHeight, { 1.f, 1.f, 1.f, 1.f });

    // Read body index map and assign colors
    k4a_image_t bodyIndexMap = k4abt_frame_get_body_index_map(bodyFrame);
    const uint8_t* bodyIndexMapBuffer = k4a_image_get_buffer(bodyIndexMap);
    for (int i = 0; i < depthWidth * depthHeight; i++)
    {
        uint8_t bodyIndex = bodyIndexMapBuffer[i];
        if (bodyIndex != K4ABT_BODY_INDEX_MAP_BACKGROUND)
        {
            uint32_t bodyId = k4abt_frame_get_body_id(bodyFrame, bodyIndex);
            pointCloudColors[i] = g_bodyColors[bodyId % g_bodyColors.size()];
        }
    }
    k4a_image_release(bodyIndexMap);



    // Visualize point cloud
    window3d.UpdatePointClouds(depthImage, pointCloudColors);

    const uint64_t timestampUsec = k4abt_frame_get_device_timestamp_usec(bodyFrame);
    const bool imageSaved = save_color_image(originalCapture, idx, folderPath);
    outputFile << "Frame Index: " << idx << "; Timestamp (usec): " << timestampUsec << std::endl;
    motionFramesFile << std::setprecision(9)
        << "{\"frame_index\":" << idx
        << ",\"timestamp_usec\":" << timestampUsec
        << ",\"image\":";
    if (imageSaved)
    {
        motionFramesFile << "\"image_idx_" << idx << ".jpg\"";
    }
    else
    {
        motionFramesFile << "null";
    }
    motionFramesFile << ",\"bodies\":[";

    // Visualize and write the skeleton data
    window3d.CleanJointsAndBones();
    uint32_t numBodies = k4abt_frame_get_num_bodies(bodyFrame);
    for (uint32_t i = 0; i < numBodies; i++)
    {
        k4abt_body_t body;
        VERIFY(k4abt_frame_get_body_skeleton(bodyFrame, i, &body.skeleton), "Get skeleton from body frame failed!");



        body.id = k4abt_frame_get_body_id(bodyFrame, i);
        print_body_information(body, outputFile);
        if (i > 0)
        {
            motionFramesFile << ',';
        }
        write_body_json(body, motionFramesFile);

        // Assign the correct color based on the body id
        Color color = g_bodyColors[body.id % g_bodyColors.size()];
        color.a = 0.4f;
        Color lowConfidenceColor = color;
        lowConfidenceColor.a = 0.1f;

        // Visualize joints
        for (int joint = 0; joint < static_cast<int>(K4ABT_JOINT_COUNT); joint++)
        {
            if (body.skeleton.joints[joint].confidence_level >= K4ABT_JOINT_CONFIDENCE_LOW)
            {
                const k4a_float3_t& jointPosition = body.skeleton.joints[joint].position;
                const k4a_quaternion_t& jointOrientation = body.skeleton.joints[joint].orientation;

                window3d.AddJoint(
                    jointPosition,
                    jointOrientation,
                    body.skeleton.joints[joint].confidence_level >= K4ABT_JOINT_CONFIDENCE_MEDIUM ? color : lowConfidenceColor);
            }
        }

        // Visualize bones
        for (size_t boneIdx = 0; boneIdx < g_boneList.size(); boneIdx++)
        {
            k4abt_joint_id_t joint1 = g_boneList[boneIdx].first;
            k4abt_joint_id_t joint2 = g_boneList[boneIdx].second;

            if (body.skeleton.joints[joint1].confidence_level >= K4ABT_JOINT_CONFIDENCE_LOW &&
                body.skeleton.joints[joint2].confidence_level >= K4ABT_JOINT_CONFIDENCE_LOW)
            {
                bool confidentBone = body.skeleton.joints[joint1].confidence_level >= K4ABT_JOINT_CONFIDENCE_MEDIUM &&
                    body.skeleton.joints[joint2].confidence_level >= K4ABT_JOINT_CONFIDENCE_MEDIUM;
                const k4a_float3_t& joint1Position = body.skeleton.joints[joint1].position;
                const k4a_float3_t& joint2Position = body.skeleton.joints[joint2].position;

                window3d.AddBone(joint1Position, joint2Position, confidentBone ? color : lowConfidenceColor);
            }
        }
    }
    motionFramesFile << "]}" << std::endl;

    k4a_capture_release(originalCapture);
    k4a_image_release(depthImage);

}

bool TrackSource(CaptureSource& source, const InputSettings& inputSettings,
    std::ofstream& outputFile, std::ofstream& motionFramesFile, const std::string& imageFolder)
{
    k4a_calibration_t sensorCalibration{};
    std::string sourceError;
    if (!source.Open(sensorCalibration, sourceError))
    {
        std::cerr << sourceError << std::endl;
        return false;
    }

    k4abt_tracker_configuration_t trackerConfig = K4ABT_TRACKER_CONFIG_DEFAULT;
    trackerConfig.processing_mode = inputSettings.processingMode;
    trackerConfig.model_path = inputSettings.ModelPath.empty() ? nullptr : inputSettings.ModelPath.c_str();
    k4abt_tracker_t tracker = nullptr;
    if (k4abt_tracker_create(&sensorCalibration, trackerConfig, &tracker) != K4A_RESULT_SUCCEEDED)
    {
        std::cerr << "Body tracker initialization failed" << std::endl;
        source.Close();
        return false;
    }

    Window3dWrapper window3d;
    window3d.Create("3D Visualization", sensorCalibration);
    window3d.SetCloseCallback(CloseCallback);
    window3d.SetKeyCallback(ProcessKey);

    const int depthWidth = sensorCalibration.depth_camera_calibration.resolution_width;
    const int depthHeight = sensorCalibration.depth_camera_calibration.resolution_height;
    const int waitTimeout = source.IsRealtime() ? 0 : K4A_WAIT_INFINITE;
    int frameIndex = 0;
    bool succeeded = true;

    while (s_isRunning)
    {
        k4a_capture_t capture = nullptr;
        const CaptureReadStatus readStatus = source.ReadCapture(&capture, waitTimeout);
        if (readStatus == CaptureReadStatus::EndOfStream)
        {
            break;
        }
        if (readStatus == CaptureReadStatus::Failed)
        {
            std::cerr << "Capture source failed while reading from " << source.DriverName() << std::endl;
            succeeded = false;
            break;
        }

        if (readStatus == CaptureReadStatus::Success)
        {
            k4a_image_t depthImage = k4a_capture_get_depth_image(capture);
            if (depthImage == nullptr)
            {
                std::cerr << "Warning: capture has no depth image; frame skipped" << std::endl;
                k4a_capture_release(capture);
            }
            else
            {
                k4a_image_release(depthImage);
                const k4a_wait_result_t queueResult =
                    k4abt_tracker_enqueue_capture(tracker, capture, waitTimeout);
                k4a_capture_release(capture);
                if (queueResult == K4A_WAIT_RESULT_FAILED)
                {
                    std::cerr << "Unable to enqueue capture for body tracking" << std::endl;
                    succeeded = false;
                    break;
                }
            }
        }

        k4abt_frame_t bodyFrame = nullptr;
        const k4a_wait_result_t popResult = k4abt_tracker_pop_result(tracker, &bodyFrame, waitTimeout);
        if (popResult == K4A_WAIT_RESULT_SUCCEEDED)
        {
            VisualizeResult(bodyFrame, window3d, depthWidth, depthHeight,
                outputFile, motionFramesFile, frameIndex, imageFolder);
            ++frameIndex;
            k4abt_frame_release(bodyFrame);
        }
        else if (popResult == K4A_WAIT_RESULT_FAILED)
        {
            std::cerr << "Unable to read body-tracking result" << std::endl;
            succeeded = false;
            break;
        }

        window3d.SetLayout3d(s_layoutMode);
        window3d.SetJointFrameVisualization(s_visualizeJointFrame);
        window3d.Render();
    }

    window3d.Delete();
    k4abt_tracker_shutdown(tracker);
    k4abt_tracker_destroy(tracker);
    source.Close();
    std::cout << "Finished body tracking from " << source.DriverName() << std::endl;
    return succeeded;
}

int main(int argc, char** argv)
{
    if (argc < 2 || argv[1] == nullptr || std::string(argv[1]).empty())
    {
        PrintUsage();
        return 2;
    }

    InputSettings inputSettings;
    std::string basePath = argv[1];
    std::error_code directoryError;
    std::filesystem::create_directories(basePath, directoryError);
    if (directoryError)
    {
        std::cerr << "Unable to create output directory: " << basePath
                  << " (" << directoryError.message() << ")" << std::endl;
        return 3;
    }
    std::error_code markerError;
    std::filesystem::remove(basePath + "\\recording.complete", markerError);
    if (markerError)
    {
        std::cerr << "Unable to remove stale recording completion marker: "
                  << markerError.message() << std::endl;
        return 7;
    }

    std::ofstream outputFile(basePath+"\\output2.txt");
    if (!outputFile.is_open())
    {
        std::cerr << "Unable to open skeleton output file in: " << basePath << std::endl;
        return 4;
    }

    std::ofstream motionFramesFile(basePath + "\\frames.jsonl");
    if (!motionFramesFile.is_open())
    {
        std::cerr << "Unable to open versioned motion frame file in: " << basePath << std::endl;
        return 5;
    }

    std::ofstream sessionLog(basePath+"\\session.log", std::ios::app);
    const auto startedAt = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    const std::tm startedLocalTime = ToLocalTime(startedAt);
    sessionLog << std::put_time(&startedLocalTime, "%Y-%m-%dT%H:%M:%S")
               << " recorder_started output=" << basePath << std::endl;
    const std::string& ImagefileFloder = basePath;
    std::cout << "Recording output: " << ImagefileFloder << std::endl;

    if (!ParseInputSettingsFromArg(argc, argv, inputSettings))
    {
        // Print app usage if user entered incorrect arguments.
        PrintUsage();
        sessionLog << "invalid_arguments" << std::endl;
        return -1;
    }

    std::string sourceError;
    std::unique_ptr<CaptureSource> captureSource = CreateCaptureSource(
        inputSettings.SourceDriver,
        inputSettings.InputPath,
        inputSettings.DepthCameraMode,
        sourceError);
    if (!captureSource)
    {
        std::cerr << sourceError << std::endl;
        sessionLog << "invalid_capture_source driver=" << inputSettings.SourceDriver << std::endl;
        return 9;
    }

    std::ofstream manifestFile(basePath + "\\session.json");
    if (!manifestFile.is_open())
    {
        std::cerr << "Unable to open motion session manifest in: " << basePath << std::endl;
        return 6;
    }
    const std::tm startedUtcTime = ToUtcTime(startedAt);
    manifestFile << "{\n"
        << "  \"format\": \"trainercam.motion-session\",\n"
        << "  \"schema_version\": 1,\n"
        << "  \"created_at\": \"" << std::put_time(&startedUtcTime, "%Y-%m-%dT%H:%M:%SZ") << "\",\n"
        << "  \"source\": { \"type\": \"azure-kinect\", \"driver\": \""
        << captureSource->DriverName() << "\", \"mode\": \""
        << (captureSource->IsRealtime() ? "live" : "recording") << "\" },\n"
        << "  \"coordinate_system\": { \"unit\": \"millimeter\", \"x_axis\": \"sensor-right\", "
        << "\"y_axis\": \"sensor-down\", \"z_axis\": \"sensor-forward\", \"orientation_order\": \"wxyz\" },\n"
        << "  \"skeleton\": { \"model\": \"azure-kinect-body-tracking\", \"joint_count\": 32 },\n"
        << "  \"files\": { \"frames\": \"frames.jsonl\", \"image_pattern\": \"image_idx_{frame_index}.jpg\", "
        << "\"legacy_frames\": \"output2.txt\" }\n"
        << "}\n";
    manifestFile.close();

    if (!TrackSource(*captureSource, inputSettings, outputFile, motionFramesFile, ImagefileFloder))
    {
        sessionLog << "capture_failed driver=" << captureSource->DriverName() << std::endl;
        return 10;
    }
    outputFile.close();
    motionFramesFile.close();
    const auto finishedAt = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    const std::tm finishedLocalTime = ToLocalTime(finishedAt);
    sessionLog << std::put_time(&finishedLocalTime, "%Y-%m-%dT%H:%M:%S")
               << " recorder_finished" << std::endl;
    sessionLog.close();
    std::ofstream completionMarker(basePath + "\\recording.complete");
    if (!completionMarker.is_open())
    {
        std::cerr << "Unable to write recording completion marker in: " << basePath << std::endl;
        return 8;
    }
    completionMarker << "complete\n";
    completionMarker.close();
    return 0;
}
