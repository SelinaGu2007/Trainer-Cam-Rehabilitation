#ifndef APPCONFIG_H
#define APPCONFIG_H

#include <QString>
#include <QStringList>
#include <QtGlobal>

struct AppConfig
{
    QString configFile;
    QString projectRoot;
    QString tutorRecordingsDir;
    QString customerRecordingsDir;
    QString logsDir;
    QString recorderProgram;
    QString videoPlayerProgram;
    QString analyzerProgram;
    QStringList analyzerPrefixArguments;
    QString exerciseProfile;
    QString subjectTrackingConfig;
    QString realtimeFeedbackConfig;
    QString captureDriver;
    QString captureDepthMode;
    QString captureProcessingMode;
    QString captureModelPath;
    QString captureRecordingPath;
    QString feedbackLocale;
    bool voiceFeedbackEnabled = true;
    double voiceRate = 0.0;
    double voiceVolume = 0.8;
    QString host;
    quint16 port = 6547;

    bool captureUsesRecording() const;
    QStringList recorderArguments(
        const QString &outputDirectory,
        const QString &recordingOverride = QString()) const;

    static const AppConfig &instance();

private:
    static AppConfig load();
};

#endif // APPCONFIG_H
