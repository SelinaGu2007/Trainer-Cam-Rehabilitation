#ifndef ANALYSE_H
#define ANALYSE_H

#include <QWidget>
#include <QDir>
#include <QShowEvent>
#include <QMessageBox>
#include <QProcess>
#include <QListWidgetItem>
#include <Windows.h>
namespace Ui {
class Analyse;
}

class Analyse : public QWidget
{
    Q_OBJECT

public:
    explicit Analyse(QWidget *parent = nullptr);
    ~Analyse();

    void displayListDirectories1(const QString& directory);
    void moveWindowAnalyse(const wchar_t* windowName,QString dirname);
private slots:
    void on_pushButtonAnalyse_clicked();
    void onShowEvent1();
    void on_pushButtonDelete_clicked();

private:
    Ui::Analyse *ui;
    QString TutorFolder = "D://Image//";
    QString MyRecordingFolder="D://Image_test//";

protected:
    void showEvent(QShowEvent *event) override;

};

#endif // ANALYSE_H
