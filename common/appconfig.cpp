#include "appconfig.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcessEnvironment>
#include <QStandardPaths>
#include <QTextStream>

#include <stdexcept>

namespace {

QString findConfigFile()
{
    const QString environmentPath = QProcessEnvironment::systemEnvironment()
                                        .value("TRAINER_CAM_CONFIG");
    if (!environmentPath.isEmpty() && QFileInfo::exists(environmentPath)) {
        return QFileInfo(environmentPath).absoluteFilePath();
    }

    const QString applicationDir = QCoreApplication::applicationDirPath();
    const QStringList candidates = {
        QDir::current().filePath("config/app.json"),
        QDir(applicationDir).filePath("config/app.json"),
        QDir(applicationDir).filePath("../config/app.json"),
        QDir(applicationDir).filePath("../../config/app.json"),
        QDir(applicationDir).filePath("../../../config/app.json")
    };

    for (const QString &candidate : candidates) {
        const QFileInfo info(candidate);
        if (info.exists() && info.isFile()) {
            return info.absoluteFilePath();
        }
    }

    throw std::runtime_error(
        "config/app.json was not found. Run from the project root or set TRAINER_CAM_CONFIG.");
}

QString requiredString(const QJsonObject &object, const QString &key)
{
    const QString value = object.value(key).toString().trimmed();
    if (value.isEmpty()) {
        throw std::runtime_error(
            QString("Missing required configuration value: %1").arg(key).toStdString());
    }
    return value;
}

QString resolvePath(const QDir &root, const QString &value)
{
    const QFileInfo info(value);
    return QDir::cleanPath(info.isAbsolute() ? value : root.filePath(value));
}

} // namespace

bool AppConfig::captureUsesRecording() const
{
    return captureDriver == "azure-kinect-recording";
}

QStringList AppConfig::recorderArguments(
    const QString &outputDirectory, const QString &recordingOverride) const
{
    QStringList arguments = {
        outputDirectory,
        "--source", captureDriver,
        "--depth-mode", captureDepthMode,
        "--processing-mode", captureProcessingMode
    };
    if (!captureModelPath.isEmpty()) {
        arguments << "--model" << captureModelPath;
    }
    if (captureUsesRecording()) {
        const QString input = recordingOverride.trimmed().isEmpty()
                                  ? captureRecordingPath
                                  : QDir::cleanPath(recordingOverride);
        if (input.isEmpty()) {
            throw std::runtime_error(
                "The configured recording capture driver requires an Azure Kinect MKV input");
        }
        const QFileInfo inputInfo(input);
        if (!inputInfo.exists() || !inputInfo.isFile()) {
            throw std::runtime_error(
                QString("Azure Kinect recording does not exist: %1").arg(input).toStdString());
        }
        arguments << "--input" << inputInfo.absoluteFilePath();
    }
    return arguments;
}

const AppConfig &AppConfig::instance()
{
    static const AppConfig config = load();
    return config;
}

AppConfig AppConfig::load()
{
    AppConfig result;
    result.configFile = findConfigFile();

    QFile file(result.configFile);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        throw std::runtime_error(
            QString("Unable to open configuration file: %1").arg(result.configFile).toStdString());
    }

    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        throw std::runtime_error(
            QString("Invalid JSON in %1: %2")
                .arg(result.configFile, parseError.errorString())
                .toStdString());
    }

    const QJsonObject rootObject = document.object();
    const QDir configDir = QFileInfo(result.configFile).absoluteDir();
    result.projectRoot = resolvePath(configDir, requiredString(rootObject, "project_root"));
    const QDir projectRoot(result.projectRoot);

    const QJsonObject paths = rootObject.value("paths").toObject();
    result.tutorRecordingsDir = resolvePath(projectRoot, requiredString(paths, "tutor_recordings"));
    result.customerRecordingsDir = resolvePath(projectRoot, requiredString(paths, "customer_recordings"));
    result.logsDir = resolvePath(projectRoot, requiredString(paths, "logs"));
    result.recorderProgram = resolvePath(projectRoot, requiredString(paths, "recorder"));
    result.videoPlayerProgram = resolvePath(projectRoot, requiredString(paths, "video_player"));
    result.analyzerProgram = resolvePath(projectRoot, requiredString(paths, "analyzer"));
    if (!QFileInfo::exists(result.analyzerProgram)) {
        const QString sourceAnalyzer = projectRoot.filePath("test_exe/main.py");
        const QString pythonProgram = QStandardPaths::findExecutable("python");
        if (QFileInfo::exists(sourceAnalyzer) && !pythonProgram.isEmpty()) {
            result.analyzerProgram = pythonProgram;
            result.analyzerPrefixArguments << QDir::cleanPath(sourceAnalyzer);
        }
    }
    const QString configuredProfile = paths.value("exercise_profile").toString().trimmed();
    result.exerciseProfile = resolvePath(
        projectRoot,
        configuredProfile.isEmpty() ? "config/exercises/arm_raise.json" : configuredProfile);
    const QString configuredTracking = paths.value("subject_tracking").toString().trimmed();
    result.subjectTrackingConfig = resolvePath(
        projectRoot,
        configuredTracking.isEmpty() ? "config/subject_tracking.json" : configuredTracking);
    const QString configuredRealtime = paths.value("realtime_feedback").toString().trimmed();
    result.realtimeFeedbackConfig = resolvePath(
        projectRoot,
        configuredRealtime.isEmpty() ? "config/realtime_feedback.json" : configuredRealtime);

    const QJsonObject capture = rootObject.value("capture").toObject();
    result.captureDriver = capture.value("driver").toString("azure-kinect-live").trimmed();
    if (result.captureDriver != "azure-kinect-live"
        && result.captureDriver != "azure-kinect-recording") {
        throw std::runtime_error(
            "capture.driver must be azure-kinect-live or azure-kinect-recording");
    }
    result.captureDepthMode = capture.value("depth_mode").toString("NFOV_UNBINNED").trimmed();
    if (result.captureDepthMode != "NFOV_UNBINNED"
        && result.captureDepthMode != "WFOV_BINNED") {
        throw std::runtime_error("capture.depth_mode is not supported");
    }
    result.captureProcessingMode = capture.value("processing_mode").toString("DIRECTML").trimmed();
    const QStringList processingModes = {"CPU", "CUDA", "DIRECTML", "TENSORRT"};
    if (!processingModes.contains(result.captureProcessingMode)) {
        throw std::runtime_error("capture.processing_mode is not supported");
    }
    const QString configuredModel = capture.value("model_path").toString().trimmed();
    result.captureModelPath = configuredModel.isEmpty()
                                  ? QString()
                                  : resolvePath(projectRoot, configuredModel);
    const QString configuredRecording = capture.value("recording_path").toString().trimmed();
    result.captureRecordingPath = configuredRecording.isEmpty()
                                      ? QString()
                                      : resolvePath(projectRoot, configuredRecording);

    const QJsonObject feedback = rootObject.value("feedback").toObject();
    result.feedbackLocale = feedback.value("locale").toString("en-US").trimmed();
    if (result.feedbackLocale != "en-US" && result.feedbackLocale != "zh-CN") {
        throw std::runtime_error("feedback.locale must be en-US or zh-CN");
    }
    result.voiceFeedbackEnabled = feedback.value("voice_enabled").toBool(true);
    result.voiceRate = feedback.value("voice_rate").toDouble(0.0);
    result.voiceVolume = feedback.value("voice_volume").toDouble(0.8);
    if (result.voiceRate < -1.0 || result.voiceRate > 1.0
        || result.voiceVolume < 0.0 || result.voiceVolume > 1.0) {
        throw std::runtime_error("feedback voice rate or volume is outside the supported range");
    }

    const QJsonObject network = rootObject.value("network").toObject();
    result.host = requiredString(network, "host");
    const int configuredPort = network.value("port").toInt(6547);
    if (configuredPort < 1 || configuredPort > 65535) {
        throw std::runtime_error("network.port must be between 1 and 65535");
    }
    result.port = static_cast<quint16>(configuredPort);

    if (!QDir().mkpath(result.tutorRecordingsDir)
        || !QDir().mkpath(result.customerRecordingsDir)
        || !QDir().mkpath(result.logsDir)) {
        throw std::runtime_error("Unable to create configured runtime directories");
    }

    return result;
}
