#include "applogger.h"

#include <QDate>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QMessageLogContext>
#include <QMutex>
#include <QMutexLocker>
#include <QTextStream>

#include <cstdio>
#include <cstdlib>

namespace {

QFile *logFile = nullptr;
QMutex logMutex;

const char *levelName(QtMsgType type)
{
    switch (type) {
    case QtDebugMsg: return "DEBUG";
    case QtInfoMsg: return "INFO";
    case QtWarningMsg: return "WARN";
    case QtCriticalMsg: return "ERROR";
    case QtFatalMsg: return "FATAL";
    }
    return "UNKNOWN";
}

void messageHandler(QtMsgType type, const QMessageLogContext &, const QString &message)
{
    const QString line = QString("%1 [%2] %3")
                             .arg(QDateTime::currentDateTime().toString(Qt::ISODateWithMs),
                                  QString::fromLatin1(levelName(type)),
                                  message);
    const QByteArray encoded = line.toLocal8Bit();
    std::fprintf(stderr, "%s\n", encoded.constData());

    QMutexLocker locker(&logMutex);
    if (logFile && logFile->isOpen()) {
        QTextStream stream(logFile);
        stream << line << Qt::endl;
    }

    if (type == QtFatalMsg) {
        std::abort();
    }
}

} // namespace

void initializeAppLogging(const QString &applicationName, const QString &logsDirectory)
{
    QDir().mkpath(logsDirectory);
    const QString filename = QDir(logsDirectory).filePath(
        QString("%1-%2.log").arg(applicationName, QDate::currentDate().toString(Qt::ISODate)));

    QMutexLocker locker(&logMutex);
    delete logFile;
    logFile = new QFile(filename);
    logFile->open(QIODevice::WriteOnly | QIODevice::Append | QIODevice::Text);
    qInstallMessageHandler(messageHandler);
}
