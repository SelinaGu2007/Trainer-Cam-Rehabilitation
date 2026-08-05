#include "mainwindow.h"

#include <QApplication>
#include <QDebug>
#include <QMessageBox>
#include "login.h"
#include "appconfig.h"
#include "applogger.h"
#include "assessmentresultdialog.h"

#include <exception>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    QApplication::setApplicationName("TrainerCam-Customer");

    try {
        const AppConfig &config = AppConfig::instance();
        initializeAppLogging("customer", config.logsDir);
        qInfo() << "Application started with config" << config.configFile;

        const QStringList arguments = a.arguments();
        const int previewIndex = arguments.indexOf("--feedback-preview");
        if (previewIndex >= 0 && previewIndex + 1 < arguments.size()) {
            const bool voiceEnabled = !arguments.contains("--no-voice")
                                      && config.voiceFeedbackEnabled;
            AssessmentResultDialog preview(
                arguments.at(previewIndex + 1),
                voiceEnabled,
                config.voiceRate,
                config.voiceVolume);
            if (!preview.isValid()) {
                QMessageBox::critical(nullptr, "Feedback preview", "Unable to read feedback summary.");
                return 2;
            }
            preview.show();
            return a.exec();
        }

        Login login;
        if (login.exec() == QDialog::Accepted) {
            MainWindow window;
            window.showMaximized();
            return a.exec();
        }
    } catch (const std::exception &error) {
        QMessageBox::critical(nullptr, "Configuration error", error.what());
        return 1;
    }

    return 0;
}
