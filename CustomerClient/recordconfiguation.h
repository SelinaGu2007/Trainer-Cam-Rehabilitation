#ifndef RECORDCONFIGUATION_H
#define RECORDCONFIGUATION_H

#include <QWidget>
#include <QDir>
#include <QTextEdit>
#include <QShowEvent>
#include <QProcess>
#include <cstdlib>
#include <iostream>
#include <array>
#include <string>
#include <cstdio>
#include <io.h>
#include <QInputDialog>
#include <QDateTime>
#include <QListWidgetItem>
#include <QDir>
#include <Windows.h>
#include <QMainWindow>
#include <QFile>
#include <QMessageBox>
#include <QStringList>
#include <QFileDialog>
namespace Ui {
class RecordConfiguation;
}

class RecordConfiguation : public QWidget
{
    Q_OBJECT

public:
    explicit RecordConfiguation(QWidget *parent = nullptr);
    ~RecordConfiguation();

    void displayListDirectories(const QString& directory);
    void moveWindowToRight(const wchar_t* windowName,QString filename);
    void moveWindowToLeft(const wchar_t* windowName,QString filename);
    void moveWindow(const wchar_t* windowName);
private:
    Ui::RecordConfiguation *ui;
    QString TutorFolder;
    QString RecordingFolder;
    QString RecorderProgram;
    QString VideoPlayerProgram;
    QString AnalyzerProgram;
    QStringList AnalyzerPrefixArguments;
    QString ExerciseProfile;
    QString SubjectTrackingConfig;
    QString RealtimeFeedbackConfig;


private slots:
    void onShowEvent();

    void on_pushButtonDispaly_clicked();

    void on_pushButtonRecord_clicked();



protected:
    void showEvent(QShowEvent *event) override;


};

#endif // RECORDCONFIGUATION_H
