#include "mainwindow.h"
#include "ui_mainwindow.h"

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
{
    ui->setupUi(this);
    server = new ServerStuff(this);
    connect(server, &ServerStuff::gotNewMesssage,
            this, &MainWindow::gotNewMesssage);
    connect(server->tcpServer, &QTcpServer::newConnection,
            this, &MainWindow::smbConnectedToServer);
    connect(server, &ServerStuff::smbDisconnected,
            this, &MainWindow::smbDisconnectedFromServer);

    connect(this,&MainWindow::showEvent,this,&MainWindow::onShowEvent);
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
   Record *R =new Record;
   R->show();
}


void MainWindow::on_pushButtonDisplay_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTask->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir1 = subdir->text();
    QString dir = CustomerFolder + subdir1;
    QString program = ".\\videoshow\\dist\\showvideo\\showvideo.exe";

    // Create process
    QProcess *process = new QProcess(this);
    process->start(program, QStringList() << "--folder" << dir);
    moveWindow(L"Tutor");
}



void MainWindow::on_pushButtonAnalyse_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTask->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir2 = subdir->text();
    QString subdir1 = subdir2.section('-', 0, 0);



    QString folder_tutor = TutorFolder+subdir1;
    QString folder_customer = CustomerFolder+subdir2;
    QString dir1 = QDir::toNativeSeparators(folder_tutor); // Ensure correct path separators
    QString dir2 = QDir::toNativeSeparators(folder_customer); // Ensure correct path separators

    QString program = ".\\test_exe\\dist\\main\\main.exe";
    QStringList arguments;
    arguments << "--folder_tutor" << dir1 << "--folder_customer" << dir2 << "--function" << "showVideos";



    QProcess *process = new QProcess(this);
    process->start(program, arguments);
    connect(process, SIGNAL(finished(int, QProcess::ExitStatus)), this, SLOT(processFinished(int, QProcess::ExitStatus)));
    connect(process, SIGNAL(errorOccurred(QProcess::ProcessError)), this, SLOT(processError(QProcess::ProcessError)));
    moveWindow(L"Ananlse_outcome",dir2+"//analyse");

}


void MainWindow::moveWindow(const wchar_t* windowName){
    for (int i=0; i<=100; i++){
        HWND hwnd = FindWindow(nullptr, windowName);

        if (hwnd != nullptr) {
            if(IsWindowVisible(hwnd)){
                // Get the screen width
                int screenWidth = GetSystemMetrics(SM_CXSCREEN);
                int screenHeight = GetSystemMetrics(SM_CYSCREEN);

                // Set the new position for the window (adjust the values as needed)
                int newX =0; // move to the right half of the screen
                int newY = 0;

                // Move the window

                MoveWindow(hwnd, newX, newY, screenWidth, screenHeight,true);// repaint the window
               // File.remove();
                break;
                }
            else{
                Sleep(100);
            }
        }
        else{
            Sleep(100);
        }
    }
}

void MainWindow::moveWindow(const wchar_t* windowName,QString dirname){
    QDir Dir(dirname);
    for( int i=0; i<=1500; i++){

        if( Dir.exists()){
            if(!Dir.isEmpty()){
                HWND hwnd = FindWindow(nullptr, windowName);
                if (hwnd != nullptr) {
                        // Get the screen width
                        int screenWidth = GetSystemMetrics(SM_CXSCREEN);
                        int screenHeight = GetSystemMetrics(SM_CYSCREEN);

                        // Set the new position for the window (adjust the values as needed)
                        int newX = 0;
                        int newY = 0;


                        MoveWindow(hwnd, newX, newY, screenWidth, screenHeight,true);// repaint the window
                       // File.remove();
                        break;

                  }
                else{
                    Sleep(100);
                }

            }
            else
                Sleep(100);

        } else {
            Sleep(100);

        }
    }
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
    if (!server->tcpServer->listen(QHostAddress::Any, 6547))
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






