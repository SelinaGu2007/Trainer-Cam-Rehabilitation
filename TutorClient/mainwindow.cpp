#include "mainwindow.h"
#include "ui_mainwindow.h"
#include "appconfig.h"

#include <QElapsedTimer>
#include <QTimer>
#include <Windows.h>

#include <memory>

namespace {

struct WindowSearchContext
{
    DWORD processId;
    HWND window = nullptr;
};

BOOL CALLBACK findVisibleProcessWindow(HWND window, LPARAM parameter)
{
    auto *context = reinterpret_cast<WindowSearchContext *>(parameter);
    DWORD ownerProcessId = 0;
    GetWindowThreadProcessId(window, &ownerProcessId);
    if (ownerProcessId == context->processId
        && IsWindowVisible(window)
        && GetWindow(window, GW_OWNER) == nullptr) {
        context->window = window;
        return FALSE;
    }
    return TRUE;
}

HWND findVisibleProcessWindow(qint64 processId)
{
    if (processId <= 0) {
        return nullptr;
    }
    WindowSearchContext context{static_cast<DWORD>(processId), nullptr};
    EnumWindows(findVisibleProcessWindow, reinterpret_cast<LPARAM>(&context));
    return context.window;
}

void fillPrimaryScreen(HWND window)
{
    MoveWindow(
        window,
        0,
        0,
        GetSystemMetrics(SM_CXSCREEN),
        GetSystemMetrics(SM_CYSCREEN),
        TRUE);
}

QString processDetails(QProcess *process)
{
    const QString standardError = QString::fromUtf8(process->readAllStandardError()).trimmed();
    return standardError.isEmpty() ? process->errorString() : standardError;
}

} // namespace

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
{
    ui->setupUi(this);
    const AppConfig &config = AppConfig::instance();
    CustomerFolder = config.customerRecordingsDir;
    TutorFolder = config.tutorRecordingsDir;
    VideoPlayerProgram = config.videoPlayerProgram;
    AnalyzerProgram = config.analyzerProgram;
    AnalyzerPrefixArguments = config.analyzerPrefixArguments;
    ExerciseProfile = config.exerciseProfile;
    SubjectTrackingConfig = config.subjectTrackingConfig;
    ServerPort = config.port;
    AnalyseButtonText = ui->pushButtonAnalyse->text();
    server = new ServerStuff(this);
    connect(server, &ServerStuff::gotNewMesssage,
            this, &MainWindow::gotNewMesssage);
    connect(server->tcpServer, &QTcpServer::newConnection,
            this, &MainWindow::smbConnectedToServer);
    connect(server, &ServerStuff::smbDisconnected,
            this, &MainWindow::smbDisconnectedFromServer);

}

MainWindow::~MainWindow()
{
    delete ui;
}


void MainWindow::displayListDirectory(const QString& directory){
    QDir dir(directory);
        QStringList dirs = dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);

        // Clear the existing items in the listWidget
        ui->listWidgetTask->clear();

        for (const QString& dirName : dirs) {
            // Create a new item for each directory
            QListWidgetItem* newItem = new QListWidgetItem(dirName);

            // Set the desired font size for the item
            QFont font = newItem->font();
            font.setPointSize(15);
            newItem->setFont(font);

            // Add the item to the listWidget
            ui->listWidgetTask->addItem(newItem);
        }
}


void MainWindow::showEvent(QShowEvent* event) {
    Q_UNUSED(event);

    displayListDirectory(CustomerFolder);// Change this to the desired directory
}


void MainWindow::onShowEvent() {
    displayListDirectory(CustomerFolder); // Change this to the desired directory
}


void MainWindow::on_pushButtonRecord_clicked()
{
    if (!RecordWindow) {
        RecordWindow = new Record(this);
    }
    RecordWindow->show();
    RecordWindow->raise();
    RecordWindow->activateWindow();
}


void MainWindow::on_pushButtonDisplay_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTask->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir1 = subdir->text();
    QString dir = QDir(CustomerFolder).filePath(subdir1);
    QString program = VideoPlayerProgram;

    // Create process
    QProcess *process = new QProcess(this);
    connect(process, &QProcess::started, this, [this, process]() {
        trackAndMoveProcessWindow(process, 10000);
    });
    connect(process, &QProcess::errorOccurred, this,
            [this, process, program](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            QMessageBox::critical(
                this,
                "Video Player Error",
                QString("Unable to start the video player: %1\n\n%2")
                    .arg(program, process->errorString()));
            process->deleteLater();
        }
    });
    connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
            process, &QObject::deleteLater);
    process->start(program, QStringList() << "--folder" << dir);
}



void MainWindow::on_pushButtonAnalyse_clicked()
{
    if (AnalyzerProcess && AnalyzerProcess->state() != QProcess::NotRunning) {
        QMessageBox::information(this, "Analysis", "Motion analysis is already running.");
        return;
    }

    QListWidgetItem *subdir = ui->listWidgetTask->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir2 = subdir->text();
    const QString referenceMarker = "-follow-";
    const int markerIndex = subdir2.lastIndexOf(referenceMarker);
    if (markerIndex <= 0) {
        QMessageBox::warning(
            this,
            "Invalid Recording",
            "The selected customer recording does not identify its tutor reference.");
        return;
    }
    const QString subdir1 = subdir2.left(markerIndex);



    QString folder_tutor = QDir(TutorFolder).filePath(subdir1);
    QString folder_customer = QDir(CustomerFolder).filePath(subdir2);
    if (!QDir(folder_tutor).exists()) {
        QMessageBox::warning(
            this,
            "Tutor Recording Missing",
            QString("Tutor recording does not exist:\n%1").arg(folder_tutor));
        return;
    }
    QString dir1 = QDir::toNativeSeparators(folder_tutor); // Ensure correct path separators
    QString dir2 = QDir::toNativeSeparators(folder_customer); // Ensure correct path separators

    QString program = AnalyzerProgram;
    QStringList arguments = AnalyzerPrefixArguments;
    arguments << "--folder_tutor" << dir1
              << "--folder_customer" << dir2
              << "--profile" << ExerciseProfile
              << "--tracking-config" << SubjectTrackingConfig
              << "--report-output" << QDir(folder_customer).filePath("assessment.json")
              << "--function" << "showVideos";



    QProcess *process = new QProcess(this);
    AnalyzerProcess = process;
    ui->pushButtonAnalyse->setEnabled(false);
    ui->pushButtonAnalyse->setText("Analyzing...");
    statusBar()->showMessage("Starting motion analysis...");
    process->setProcessChannelMode(QProcess::SeparateChannels);
    connect(process, &QProcess::started, this, [this, process]() {
        statusBar()->showMessage("Motion analysis is running...");
        trackAndMoveProcessWindow(process, 150000);
    });
    connect(process, &QProcess::errorOccurred, this, [this, process, program](QProcess::ProcessError error) {
        if (error != QProcess::FailedToStart || AnalyzerProcess != process) {
            return;
        }
        QMessageBox::critical(
            this,
            "Analysis Error",
            QString("Unable to start the motion analyzer: %1\n\n%2")
                .arg(program, process->errorString()));
        finishAnalysisProcess(process, "Unable to start motion analysis.");
    });
    connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
            this, [this, process](int exitCode, QProcess::ExitStatus exitStatus) {
        if (AnalyzerProcess != process) {
            process->deleteLater();
            return;
        }
        const QString details = processDetails(process);
        const QString suffix = details.isEmpty() ? QString() : "\n\n" + details;
        if (exitStatus != QProcess::NormalExit) {
            QMessageBox::critical(
                this,
                "Analysis Error",
                "The motion analyzer stopped unexpectedly." + suffix);
        } else if (exitCode == 10) {
            QMessageBox::warning(
                this,
                "Session Quality Check",
                "The recording did not meet the required tracking or joint quality." + suffix);
        } else if (exitCode == 2 || exitCode == 20) {
            QMessageBox::critical(
                this,
                "Analysis Input Error",
                "The recording or analysis configuration is invalid." + suffix);
        } else if (exitCode != 0) {
            QMessageBox::critical(
                this,
                "Analysis Error",
                "The analyzer stopped because of an unexpected internal error." + suffix);
        }
        finishAnalysisProcess(
            process,
            exitStatus == QProcess::NormalExit && exitCode == 0
                ? "Motion analysis completed."
                : "Motion analysis failed.");
    });
    process->start(program, arguments);
}

void MainWindow::trackAndMoveProcessWindow(QProcess *process, int timeoutMs)
{
    auto *timer = new QTimer(this);
    auto elapsed = std::make_shared<QElapsedTimer>();
    QPointer<QProcess> processGuard(process);
    elapsed->start();

    connect(timer, &QTimer::timeout, this,
            [timer, elapsed, processGuard, timeoutMs]() {
        if (!processGuard) {
            timer->stop();
            timer->deleteLater();
            return;
        }
        if (HWND window = findVisibleProcessWindow(processGuard->processId())) {
            fillPrimaryScreen(window);
            timer->stop();
            timer->deleteLater();
            return;
        }
        if (elapsed->elapsed() >= timeoutMs
            || processGuard->state() == QProcess::NotRunning) {
            timer->stop();
            timer->deleteLater();
        }
    });
    timer->start(100);
}

void MainWindow::finishAnalysisProcess(QProcess *process, const QString &statusMessage)
{
    if (AnalyzerProcess != process) {
        return;
    }
    AnalyzerProcess = nullptr;
    ui->pushButtonAnalyse->setEnabled(true);
    ui->pushButtonAnalyse->setText(AnalyseButtonText);
    statusBar()->showMessage(statusMessage, 5000);
    process->deleteLater();
}



//networkchat
void MainWindow::smbConnectedToServer()
{
    QString username = QProcessEnvironment::systemEnvironment().value("USERNAME"); // For Windows
    // QString username = QProcessEnvironment::systemEnvironment().value("USER"); // For Unix-like systems
    QString hostname = QHostInfo::localHostName();
    QString port = QString::number(server->tcpServer->serverPort()); // Change this to the actual port

    QString logMessage = QString("%1@%2:%3 connected").arg(username, hostname, port);
    ui->textEditLog->append(logMessage);
    //ui->textEditLog->append(tr("Somebody has connected"));
}

void MainWindow::smbDisconnectedFromServer()
{
    QString username = QProcessEnvironment::systemEnvironment().value("USERNAME"); // For Windows
    // QString username = QProcessEnvironment::systemEnvironment().value("USER"); // For Unix-like systems
    QString hostname = QHostInfo::localHostName();
    QString port = QString::number(server->tcpServer->serverPort()); // Change this to the actual port

    QString logMessage = QString("%1@%2:%3 disconnected").arg(username, hostname, port);
    ui->textEditLog->append(logMessage);
    //ui->textEditLog->append(tr("Somebody has disconnected"));
}

void MainWindow::gotNewMesssage(QString msg)
{
    QString username = QProcessEnvironment::systemEnvironment().value("USERNAME"); // For Windows
    // QString username = QProcessEnvironment::systemEnvironment().value("USER"); // For Unix-like systems
    QString hostname = QHostInfo::localHostName();
    QString port = QString::number(server->tcpServer->serverPort()); // Change this to the actual port

    QString logMessage = QString(" %1@%2:%3: %4").arg(username, hostname, port, msg);
    ui->textEditLog->append(logMessage);
    //ui->textEditLog->append(QString("New message: %1").arg(msg));
}

void MainWindow::on_pushButtonConnection_clicked()
{
    if (!server->tcpServer->listen(QHostAddress::Any, ServerPort))
    {
        ui->textEditLog->append(tr("<font color=\"red\"><b>Error!</b> The port is taken by some other service.</font>"));
        return;
    }
    connect(server->tcpServer, &QTcpServer::newConnection, server, &ServerStuff::newConnection);
    ui->textEditLog->append(tr("<font color=\"green\"><b>Server started</b>, port is openned.</font>"));
}


void MainWindow::on_pushButtonSend_clicked()
{

    QString msg = ui->lineEditMessage->text();
    for (QTcpSocket *clientSocket : server->getClients()) {
        server->sendToClient(clientSocket, "tutor:"+msg);
    }
    ui->textEditLog->append("me: "+msg);
    ui->lineEditMessage->clear();
}


void MainWindow::on_pushButtonDisconnection_clicked()
{
    if(server->tcpServer->isListening())
    {
        disconnect(server->tcpServer, &QTcpServer::newConnection, server, &ServerStuff::newConnection);

        QList<QTcpSocket *> clients = server->getClients();
        for(int i = 0; i < clients.count(); i++)
        {
            //server->sendToClient(clients.at(i), "Connection closed");
            server->sendToClient(clients.at(i), "0");
        }

        server->tcpServer->close();
        ui->textEditLog->append(tr("<b>Server stopped</b>, post is closed"));
    }
    else
    {
        ui->textEditLog->append(tr("<b>Error!</b> Server was not running"));
    }
}






