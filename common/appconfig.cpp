#include "appconfig.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcessEnvironment>
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
    const QString configuredProfile = paths.value("exercise_profile").toString().trimmed();
    result.exerciseProfile = resolvePath(
        projectRoot,
        configuredProfile.isEmpty() ? "config/exercises/arm_raise.json" : configuredProfile);

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
