#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include "ClientStuff.h"
#include<QCoreApplication>
#include <QCloseEvent>
QT_BEGIN_NAMESPACE
namespace Ui { class MainWindow; }
QT_END_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();
public slots:

    void receivedSomething(QString msg);
    void gotError(QAbstractSocket::SocketError err);

private slots:
    void on_pushButtonConnection_clicked();

    void on_pushButtonDisconnection_clicked();

    void on_pushButtonSend_clicked();

    void on_pushButtonRecord_clicked();

    void on_pushButtonAnalyse_clicked();

private:
    Ui::MainWindow *ui;
    ClientStuff *client;

protected:
    void closeEvent(QCloseEvent *event) override;
};
#endif // MAINWINDOW_H
