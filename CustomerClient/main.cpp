#include "mainwindow.h"

#include <QApplication>
#include <QDebug>
#include <QMessageBox>
#include "login.h"
#include "appconfig.h"
#include "applogger.h"
#include "assessmentresultdialog.h"
#include "assessmentreviewdialog.h"

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
        const int reviewIndex = arguments.indexOf("--review-preview");
        if (reviewIndex >= 0 && reviewIndex + 3 < arguments.size()) {
            QString locale = "en-US";
            const int localeIndex = arguments.indexOf("--locale");
            if (localeIndex >= 0 && localeIndex + 1 < arguments.size()) {
                locale = arguments.at(localeIndex + 1);
            }
            AssessmentReviewDialog preview(
                arguments.at(reviewIndex + 1),
                arguments.at(reviewIndex + 2),
                arguments.at(reviewIndex + 3),
                locale);
            if (!preview.isValid()) {
                QMessageBox::critical(nullptr, "Review preview", "Unable to read session review data.");
                return 2;
            }
            preview.show();
            return a.exec();
        }
        const int previewIndex = arguments.indexOf("--feedback-preview");
        if (previewIndex >= 0 && previewIndex + 1 < arguments.size()) {
            const bool voiceEnabled = !arguments.contains("--no-voice")
                                      && config.voiceFeedbackEnabled;
            const auto optionalValue = [&arguments](const QString &flag) {
                const int index = arguments.indexOf(flag);
                return index >= 0 && index + 1 < arguments.size()
                           ? arguments.at(index + 1)
                           : QString();
            };
            AssessmentResultDialog preview(
                arguments.at(previewIndex + 1),
                voiceEnabled,
                config.voiceRate,
                config.voiceVolume,
                nullptr,
                optionalValue("--review"),
                optionalValue("--customer-folder"),
                optionalValue("--tutor-folder"));
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
