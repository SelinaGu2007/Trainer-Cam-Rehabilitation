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
    QString host;
    quint16 port = 6547;

    static const AppConfig &instance();

private:
    static AppConfig load();
};

#endif // APPCONFIG_H
