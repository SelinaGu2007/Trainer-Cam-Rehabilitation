#ifndef RECORD_H
#define RECORD_H

#include <QWidget>
#include <QDir>
#include <QProcess>
#include <QShowEvent>
#include <QListWidgetItem>
#include <QMessageBox>
#include <Windows.h>
#include <QInputDialog>
namespace Ui {
class Record;
}

class Record : public QWidget
{
    Q_OBJECT

public:
    explicit Record(QWidget *parent = nullptr);
    ~Record();

     void displayListDirectories(const QString& directory);
     void moveWindowToMiddle(const wchar_t* windowName,QString filename);
private slots:
    void on_pushButtonRecord_clicked();
    void onShowEvent();

    void on_pushButtonDispaly_clicked();


    void on_pushButtonDelete_clicked();

private:
    Ui::Record *ui;
    QString TutorFolder ="D:\\Image\\";

protected:
    void showEvent(QShowEvent *event) override;
};

#endif // RECORD_H
