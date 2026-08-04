#include "mainwindow.h"

#include <QApplication>
#include <QDebug>
#include <QMessageBox>
#include "login.h"
#include "appconfig.h"
#include "applogger.h"

#include <exception>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    QApplication::setApplicationName("TrainerCam-Customer");

    try {
        const AppConfig &config = AppConfig::instance();
        initializeAppLogging("customer", config.logsDir);
        qInfo() << "Application started with config" << config.configFile;

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
