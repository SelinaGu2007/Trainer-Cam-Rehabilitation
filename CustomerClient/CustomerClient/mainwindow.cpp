#include "mainwindow.h"
#include "ui_mainwindow.h"
#include "recordconfiguation.h"
#include "analyse.h"
MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
{
    ui->setupUi(this);
    client = new ClientStuff("localhost", 6547);
    connect(client, &ClientStuff::hasReadSome, this, &MainWindow::receivedSomething);
    // FIXME change this connection to the new syntax
    connect(client->tcpSocket, SIGNAL(error(QAbstractSocket::SocketError)),
            this, SLOT(gotError(QAbstractSocket::SocketError)));
    connect(this, &MainWindow::destroyed, QCoreApplication::instance(), &QCoreApplication::quit);
}

MainWindow::~MainWindow()
{
    delete ui;
}


void MainWindow::closeEvent(QCloseEvent *event)
{
    // Emit the destroyed signal explicitly when the MainWindow is closed
    emit destroyed();
    QMainWindow::closeEvent(event);
}

void MainWindow::on_pushButtonRecord_clicked()
{
    RecordConfiguation *RC = new RecordConfiguation;
  //  RC->show();
    RC->showNormal();
}


void MainWindow::on_pushButtonAnalyse_clicked()
{
    Analyse *w = new Analyse;
    w->showNormal();

}


//newwork_chat
void MainWindow::receivedSomething(QString msg)
{
    ui->textEditLog->append(msg);
}

void MainWindow::gotError(QAbstractSocket::SocketError err)
{
    //qDebug() << "got error";
    QString strError = "unknown";
    switch (err)
    {
        case 0:
            strError = "Connection was refused";
            break;
        case 1:
            strError = "Remote host closed the connection";
            break;
        case 2:
            strError = "Host address was not found";
            break;
        case 5:
            strError = "Connection timed out";
            break;
        default:
            strError = "Unknown error";
    }

    ui->textEditLog->append(strError);
}


void MainWindow::on_pushButtonSend_clicked()
{
    QByteArray arrBlock;
    QDataStream out(&arrBlock, QIODevice::WriteOnly);
    //out.setVersion(QDataStream::Qt_5_10);
    out << quint16(0) << ui->lineEditMessage->text();

    out.device()->seek(0);
    out << quint16(arrBlock.size() - sizeof(quint16));
    client->tcpSocket->write(arrBlock);
    ui->lineEditMessage->clear();
}


void MainWindow::on_pushButtonConnection_clicked()
{
      client->connect2host();
}


void MainWindow::on_pushButtonDisconnection_clicked()
{
    client->closeConnection();
}



