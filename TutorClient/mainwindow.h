#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include "serverstuff.h"
#include <QHostInfo>
#include <QSysInfo>
#include <QProcessEnvironment>
#include <QListWidgetItem>
#include <QShowEvent>
#include "record.h"
QT_BEGIN_NAMESPACE
namespace Ui { class MainWindow; }
QT_END_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();
    void displayListDirectory(const QString& directory);
    void moveWindow(const wchar_t* windowName);
    void moveWindow(const wchar_t* windowName,QString dirname);
private slots:
    void on_pushButtonConnection_clicked();

    void on_pushButtonDisconnection_clicked();

    void on_pushButtonSend_clicked();

    void onShowEvent();
    void smbConnectedToServer();
    void smbDisconnectedFromServer();
    void gotNewMesssage(QString msg);

    void on_pushButtonRecord_clicked();

    void on_pushButtonDisplay_clicked();

    void on_pushButtonAnalyse_clicked();

private:
    Ui::MainWindow *ui;
    ServerStuff *server;
    QString CustomerFolder = "D:\\Image_test\\";
    QString TutorFolder ="D:\\Image\\";

protected:
    void showEvent(QShowEvent *event) override;
};
#endif // MAINWINDOW_H
